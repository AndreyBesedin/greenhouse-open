import Ajv2020 from "ajv/dist/2020";

import { SNAPSHOT_SCHEMA } from "./generated/snapshotSchema";
import type { SceneSnapshot } from "./generated/snapshotTypes";

// The snapshot schema version this viewer draws. The simulator bumps it when
// a change would break an existing viewer.
export const SUPPORTED_SCHEMA_VERSION = 1;

const validate = new Ajv2020({ allErrors: true, strict: true }).compile<SceneSnapshot>(
  SNAPSHOT_SCHEMA,
);

export type SceneCheck = { ok: true; snapshot: SceneSnapshot } | { ok: false; problems: string[] };

/** A scene checked against the schema the simulator publishes, rather than trusted. */
export function checkScene(body: unknown): SceneCheck {
  if (!validate(body)) {
    const problems = (validate.errors ?? []).map(
      (error) => `${error.instancePath || "the scene"} ${error.message ?? "is not valid"}`,
    );
    return { ok: false, problems };
  }
  if (body.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    return {
      ok: false,
      problems: [
        `schema version ${body.schema_version} is not the ${SUPPORTED_SCHEMA_VERSION} this viewer draws`,
      ],
    };
  }
  return { ok: true, snapshot: body };
}
