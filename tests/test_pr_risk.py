from typing import Any

from scripts.check_pr_risk import ROOT, SENSITIVE_FILES, _risk_reasons, approved

HEAD = "b" * 40
EARLIER = "a" * 40


def _review(
    state: str, commit: str = HEAD, user: str = "maintainer", association: str = "OWNER"
) -> dict[str, Any]:
    return {"user": user, "state": state, "commit_id": commit, "author_association": association}


def test_every_sensitive_path_exists() -> None:
    """A sensitive file that moves must take its entry with it. Otherwise the
    gate silently stops flagging changes to it."""
    missing = sorted(path for path in SENSITIVE_FILES if not (ROOT / path).exists())
    assert not missing, f"sensitive paths that no longer exist: {missing}"


def test_small_single_package_change_is_normal_risk() -> None:
    assert (
        _risk_reasons(["greenhouse_sim/greenhouse_sim/biology/tomato/simple/growth.py"], 80) == []
    )


def test_large_change_requires_manual_review() -> None:
    reasons = _risk_reasons(["greenhouse_sim/greenhouse_sim/foo.py"], 501)
    assert any("> 500" in reason for reason in reasons)


def test_protocol_change_requires_manual_review() -> None:
    reasons = _risk_reasons(["greenhouse_protocol/greenhouse_protocol/observation.py"], 20)
    assert "shared protocol/package contract changed" in reasons


def test_cross_package_change_requires_manual_review() -> None:
    reasons = _risk_reasons(
        [
            "greenhouse_sim/greenhouse_sim/engine.py",
            "greenhouse_adapters/greenhouse_adapters/cli.py",
        ],
        30,
    )
    assert any("multiple publishable packages" in reason for reason in reasons)


def test_ci_change_requires_manual_review() -> None:
    reasons = _risk_reasons([".github/workflows/ci.yml"], 10)
    assert "GitHub CI/review automation changed" in reasons


def test_a_maintainers_approval_of_the_latest_commit_acknowledges_it() -> None:
    assert approved([_review("APPROVED")], HEAD)
    assert approved([_review("APPROVED", association="COLLABORATOR")], HEAD)


def test_without_an_approval_there_is_no_acknowledgement() -> None:
    assert not approved([], HEAD)
    assert not approved([_review("COMMENTED")], HEAD)


def test_an_approval_of_an_earlier_commit_does_not_cover_a_later_push() -> None:
    assert not approved([_review("APPROVED", commit=EARLIER)], HEAD)


def test_anyone_but_a_maintainer_approves_for_nothing() -> None:
    for association in ("CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "NONE"):
        assert not approved([_review("APPROVED", association=association)], HEAD)


def test_a_later_verdict_withdraws_an_approval_and_a_comment_does_not() -> None:
    assert not approved([_review("APPROVED"), _review("CHANGES_REQUESTED")], HEAD)
    assert not approved([_review("DISMISSED")], HEAD)
    assert approved([_review("APPROVED"), _review("COMMENTED")], HEAD)
    assert approved([_review("CHANGES_REQUESTED"), _review("APPROVED")], HEAD)


def test_one_maintainers_approval_is_enough() -> None:
    reviews = [_review("COMMENTED", user="other"), _review("APPROVED")]
    assert approved(reviews, HEAD)
