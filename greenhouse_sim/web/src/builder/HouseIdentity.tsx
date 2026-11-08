import { type FormEvent, useId, useState } from "react";

import { Button } from "../design/Button";
import { Field } from "../design/Field";

/**
 * A draft's identifier and name, changed as an edit is, undone in one step
 * (P12.2): a draft started from a file or a scenario under an identifier
 * kept already is saved under another; a draft saved is saved, under a new
 * identifier, as a new draft.
 */
export function HouseIdentity({
  draftId,
  name,
  onRename,
}: {
  draftId: string;
  name: string;
  onRename: (draftId: string, name: string) => void;
}) {
  const heading = useId();
  // What is typed, until it is applied; what the draft holds otherwise, so
  // that an undo shows its own.
  const [typed, setTyped] = useState<{ draftId: string; name: string } | null>(null);
  const shown = typed ?? { draftId, name };

  function rename(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setTyped(null);
    onRename(shown.draftId.trim(), shown.name.trim());
  }

  return (
    <form className="builder-identity" aria-labelledby={heading} onSubmit={rename}>
      <h2 id={heading}>The house</h2>
      <Field label="Identifier" size="compact" className="builder-field">
        {(control) => (
          <input
            {...control}
            required
            value={shown.draftId}
            onChange={(event) => setTyped({ ...shown, draftId: event.target.value })}
          />
        )}
      </Field>
      <Field label="Name" size="compact" className="builder-field">
        {(control) => (
          <input
            {...control}
            required
            value={shown.name}
            onChange={(event) => setTyped({ ...shown, name: event.target.value })}
          />
        )}
      </Field>
      <Button
        type="submit"
        size="compact"
        disabled={typed === null || (typed.draftId === draftId && typed.name === name)}
      >
        Rename
      </Button>
    </form>
  );
}
