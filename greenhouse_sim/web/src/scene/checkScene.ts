import { contractCheck } from "../loadJson";
import { SNAPSHOT_SCHEMA } from "./generated/snapshotSchema";
import type { SceneSnapshot } from "./generated/snapshotTypes";
import { SUPPORTED_SCHEMA_VERSION } from "./schemaVersion";

export { SUPPORTED_SCHEMA_VERSION };

const checkSnapshot = contractCheck<SceneSnapshot>(SNAPSHOT_SCHEMA, "the scene");

export type SceneCheck = { ok: true; snapshot: SceneSnapshot } | { ok: false; problems: string[] };

/** A scene checked against the schema the simulator publishes, rather than trusted. */
export function checkScene(body: unknown): SceneCheck {
  const checked = checkSnapshot(body);
  if (!checked.ok) {
    return checked;
  }
  const snapshot = checked.value;
  if (snapshot.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    return {
      ok: false,
      problems: [
        `schema version ${snapshot.schema_version} is not the ${SUPPORTED_SCHEMA_VERSION} this viewer draws`,
      ],
    };
  }
  return { ok: true, snapshot };
}
