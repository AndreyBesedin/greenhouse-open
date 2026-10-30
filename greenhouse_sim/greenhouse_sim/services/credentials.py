"""Who a request over the network comes from (P15.5, decision 0061): a
credentials file, given to a server as an authorisation file is
(decision 0052).

Each credential names a principal, its role and the SHA-256 of its bearer
token, never the token itself, so that the file reveals no token. A
request carries its token (`Authorization: Bearer <token>`), and the
server finds the credential whose hash is the token's. Three roles are
told apart:

- **a policy** reads its port and gives plans as itself;
- **the operator** keeps the local API, which authenticates no one;
- **an evaluator** reads the evaluation's outputs, in the process.

A policy's port serves policies alone. A token is made by
`new_credential`, which gives it once, to be handed to its holder; the
file keeps its hash.
"""

import hashlib
import hmac
import secrets
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal, Self

from greenhouse_protocol.plan import Principal
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError, model_validator

from greenhouse_sim.services.errors import InvalidRequest, every_reason, first_reason

CREDENTIALS_VERSION: Final = 1
# How many random bytes a token holds: 256 bits, written in URL-safe base64.
TOKEN_BYTES: Final = 32

type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Role(StrEnum):
    POLICY = "policy"
    OPERATOR = "operator"
    EVALUATOR = "evaluator"


class Credential(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    principal: Principal
    role: Role
    token_sha256: Sha256


class Credentials(BaseModel):
    """A server's credentials: see the module."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1] = CREDENTIALS_VERSION
    credentials: tuple[Credential, ...]

    @model_validator(mode="after")
    def _each_once(self) -> Self:
        hashes = [credential.token_sha256 for credential in self.credentials]
        if len(set(hashes)) != len(hashes):
            raise ValueError("a token is given to more than one credential")
        principals = [credential.principal for credential in self.credentials]
        if len(set(principals)) != len(principals):
            raise ValueError("a principal has more than one credential")
        return self

    def holder(self, token: str) -> Credential | None:
        """The credential whose token `token` is, or None: compared as
        hashes, in a time that does not tell how much of one matched."""
        given = hashed(token)
        found = None
        for credential in self.credentials:
            if hmac.compare_digest(credential.token_sha256, given):
                found = credential
        return found


def hashed(token: str) -> str:
    """A token's SHA-256, as a credential keeps it."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_credential(principal: Principal, role: Role = Role.POLICY) -> tuple[str, Credential]:
    """A new token for `principal`, and its credential: the token to hand to
    its holder, the credential to keep in the file."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, Credential(principal=principal, role=role, token_sha256=hashed(token))


def new_credential_for(spelled: str) -> tuple[str, Credential]:
    """A new token and its credential for the policy a command line spells
    as `kind:id`, such as `policy:naive_heating`."""
    kind, _, identity = spelled.partition(":")
    try:
        principal = Principal.model_validate({"kind": kind, "id": identity})
    except ValidationError as error:
        raise InvalidRequest(
            f"a principal is spelled kind:id, such as policy:naive_heating, not {spelled!r}: "
            f"{first_reason(error)}"
        ) from None
    return new_credential(principal)


def credentials_file(path: Path) -> Credentials:
    """The credentials a JSON file holds, or refused, saying why."""
    try:
        text = path.read_text()
    except OSError as error:
        raise InvalidRequest(f"no credentials in {path}: {error.strerror}") from None
    try:
        return Credentials.model_validate_json(text)
    except ValidationError as error:
        raise InvalidRequest(
            f"not credentials in {path}: {first_reason(error)}", every_reason(error)
        ) from None
