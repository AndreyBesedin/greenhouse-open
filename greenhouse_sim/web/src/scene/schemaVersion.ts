// The snapshot schema version this viewer draws. The simulator bumps it when
// a change would break an existing viewer. Kept apart from the scene check so
// that scene builders and browser tests can read it without the validator.
export const SUPPORTED_SCHEMA_VERSION = 5;
