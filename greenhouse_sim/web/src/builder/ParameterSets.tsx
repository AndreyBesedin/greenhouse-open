import { type FormEvent, type ReactNode, useEffect, useId, useState } from "react";

import { Button } from "../design/Button";
import { Field } from "../design/Field";
import { Fold } from "../design/Fold";
import { Notice } from "../design/Notice";
import type { Loaded } from "../loadJson";
import {
  changedValue,
  compareSets,
  downloadSet,
  loadParametersSchema,
  loadSet,
  loadSets,
  newVersion,
  type SetComparison,
  type SetKey,
  type SetListed,
  type SetRead,
  saveSet,
  setName,
  type VersionForm,
} from "./parameterSetLibrary";
import { offerFile } from "./scenarioFile";
import { type ParameterField, parameterFields, rangeText } from "./schemaForm";

/** A model's sets and the fields of its parameters, as the simulator serves
 * them. */
interface Library {
  sets: SetListed[];
  fields: ParameterField[];
}

const EMPTY_FORM: VersionForm = { name: "", cultivar: "", description: "", values: {}, why: {} };

const sameKey = (a: SetKey, b: SetKey) => a.name === b.name && a.version === b.version;

/** What a parameter takes, in words: its unit, and its range or why it is
 * fixed. */
function takes(field: ParameterField): string {
  const unit = field.unit === "" || field.unit === "-" ? "No unit" : `In ${field.unit}`;
  return field.fixed === null ? `${unit}, ${rangeText(field)}.` : `${unit}. Fixed: ${field.fixed}.`;
}

/** A number as the form shows it: as JSON writes it, which reads back the same. */
function shown(value: number | undefined): string {
  return value === undefined ? "" : String(value);
}

/** The form's values as a set gives them, each as an input holds it. */
function formOf(set: SetRead, kept: VersionForm): VersionForm {
  const values = Object.fromEntries(
    Object.entries(set.values).map(([name, value]) => [name, shown(value)]),
  );
  return { ...kept, values, why: {} };
}

function ParameterValue({
  field,
  base,
  form,
  problems,
  onValue,
  onWhy,
}: {
  field: ParameterField;
  base: SetRead;
  form: VersionForm;
  problems: Readonly<Record<string, string>>;
  onValue: (text: string) => void;
  onWhy: (text: string) => void;
}) {
  const changed = changedValue(form.values[field.name], base.values[field.name] ?? Number.NaN);
  const { least, most } = field;
  return (
    <div className="builder-parameter">
      <Field
        label={field.what}
        hint={takes(field)}
        problem={problems[`parameters.${field.name}`]}
        size="compact"
        className="builder-give-field"
      >
        {(control) => (
          <input
            {...control}
            name={field.name}
            type="number"
            step="any"
            // The simulator says what is outside the range; an input bounds
            // only what its ends allow.
            min={least === null || least.exclusive ? undefined : least.value}
            max={most === null || most.exclusive ? undefined : most.value}
            readOnly={field.fixed !== null}
            placeholder={shown(base.values[field.name])}
            value={form.values[field.name] ?? ""}
            onChange={(event) => onValue(event.target.value)}
          />
        )}
      </Field>
      {changed !== null && (
        <Field
          label={`Why ${field.name}`}
          hint="Where its value comes from: a calibration, a publication, a measurement."
          problem={problems[`why.${field.name}`]}
          size="compact"
          className="builder-give-field"
        >
          {(control) => (
            <input
              {...control}
              value={form.why[field.name] ?? ""}
              onChange={(event) => onWhy(event.target.value)}
            />
          )}
        </Field>
      )}
      <Fold summary="Where it comes from" className="builder-parameter-source">
        <p>{field.source}</p>
        <p>
          Its least{least === null ? "" : `, ${least.value}`}: {field.leastFrom}
        </p>
        <p>
          Its most{most === null ? "" : `, ${most.value}`}: {field.mostFrom}
        </p>
      </Fold>
    </div>
  );
}

function Comparison({ comparison }: { comparison: SetComparison }) {
  const first = setName(comparison.first);
  const second = setName(comparison.second);
  const count = comparison.changes.length;
  if (count === 0) {
    return (
      <p className="builder-note" data-testid="parameter-set-comparison">
        {second} gives every parameter the value its base, {first}, gives.
      </p>
    );
  }
  return (
    <table className="builder-comparison" data-testid="parameter-set-comparison">
      <caption>
        {second} against its base, {first}: {count}{" "}
        {count === 1 ? "parameter differs" : "parameters differ"}
      </caption>
      <thead>
        <tr>
          <th scope="col">Parameter</th>
          <th scope="col">{first}</th>
          <th scope="col">{second}</th>
        </tr>
      </thead>
      <tbody>
        {comparison.changes.map((change) => (
          <tr key={change.name}>
            <th scope="row">{change.name}</th>
            <td>{change.first}</td>
            <td>{change.second}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * The parameter sets of the crop model the house's rows grow (P20.5, decision
 * 0077): one chosen, compared with its base and downloaded as its file; and a
 * new version edited from it, each parameter as its model's schema describes
 * it, with its unit, source and range, a fixed one read only with why. The
 * simulator saves it under its name's next version, or refuses it by field: a
 * value outside its range, a value changed without why, a name taken by the
 * published set.
 *
 * It shows one model's sets: the builder keys it by the model, so that what was
 * asked of another model's is never shown with this one's.
 */
export function ParameterSets({ model }: { model: string | null }) {
  const heading = useId();
  const formHeading = useId();
  const [library, setLibrary] = useState<Loaded<Library> | null>(null);
  const [chosen, setChosen] = useState<SetKey | null>(null);
  const [base, setBase] = useState<SetRead | null>(null);
  const [form, setForm] = useState<VersionForm>(EMPTY_FORM);
  const [problems, setProblems] = useState<Readonly<Record<string, string>>>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [comparison, setComparison] = useState<SetComparison | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let current = true;
    setLibrary(null);
    setChosen(null);
    setBase(null);
    setComparison(null);
    setProblems({});
    setProblem(null);
    setStatus("");
    if (model === null) {
      return;
    }
    void (async () => {
      const [sets, schema] = await Promise.all([loadSets(model), loadParametersSchema(model)]);
      if (!current) {
        return;
      }
      if (sets.status !== "loaded") {
        setLibrary(sets);
        return;
      }
      if (schema.status !== "loaded") {
        setLibrary(schema);
        return;
      }
      setLibrary({
        status: "loaded",
        value: { sets: sets.value, fields: parameterFields(schema.value) },
      });
      const published = sets.value.find((each) => each.published) ?? sets.value[0];
      setChosen(
        published === undefined ? null : { name: published.name, version: published.version },
      );
    })();
    return () => {
      current = false;
    };
  }, [model]);

  useEffect(() => {
    let current = true;
    setComparison(null);
    if (model === null || chosen === null) {
      return;
    }
    void (async () => {
      const read = await loadSet(model, chosen);
      if (!current) {
        return;
      }
      if (read.status !== "loaded") {
        setBase(null);
        setProblem(`${setName(chosen)} cannot be read: ${read.reason}`);
        return;
      }
      setBase(read.value);
      setForm((kept) => formOf(read.value, kept));
      setProblems({});
      setProblem(null);
    })();
    return () => {
      current = false;
    };
  }, [model, chosen]);

  if (model === null) {
    return (
      <Section heading={heading}>
        <p className="builder-note">The rows grow no crop yet.</p>
      </Section>
    );
  }
  if (library === null) {
    return (
      <Section heading={heading}>
        <p className="builder-note">Asking for {model}'s parameter sets.</p>
      </Section>
    );
  }
  if (library.status !== "loaded") {
    return (
      <Section heading={heading}>
        <p className="builder-note" data-testid="parameter-sets-unavailable">
          The rows grow {model}: {library.reason}.
        </p>
      </Section>
    );
  }
  const { sets, fields } = library.value;
  const madeFor = sets.find((each) => each.published)?.made_for;
  const listedChosen = chosen === null ? undefined : sets.find((each) => sameKey(each, chosen));

  async function compare(): Promise<void> {
    const basedOn = base?.based_on;
    if (model === null || base === null || basedOn == null) {
      return;
    }
    setBusy(true);
    const answer = await compareSets(model, basedOn, base);
    setBusy(false);
    if (answer.status !== "loaded") {
      setProblem(`They cannot be compared: ${answer.reason}`);
      return;
    }
    setProblem(null);
    setComparison(answer.value);
  }

  async function download(): Promise<void> {
    if (model === null || base === null) {
      return;
    }
    const answer = await downloadSet(model, base);
    if (answer.status !== "loaded") {
      setProblem(`Its file cannot be made: ${answer.reason}`);
      return;
    }
    offerFile(answer.value.file_name, answer.value.text);
  }

  async function save(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (model === null || base === null || madeFor === undefined) {
      return;
    }
    setBusy(true);
    setStatus("");
    const answer = await saveSet(model, newVersion(base, form, madeFor));
    if (!answer.ok) {
      setBusy(false);
      setProblems(answer.fields);
      setProblem(`Not saved: ${answer.problem}`);
      return;
    }
    // The list again, with the version saved in it.
    const kept = await loadSets(model);
    setBusy(false);
    if (kept.status === "loaded") {
      setLibrary({ status: "loaded", value: { sets: kept.value, fields } });
    }
    const saved = answer.value;
    setProblems({});
    setProblem(null);
    setStatus(`Saved as ${setName(saved)}, ${saved.digest}.`);
    setChosen({ name: saved.name, version: saved.version });
  }

  function typed(name: string, text: string): void {
    setForm((now) => ({ ...now, values: { ...now.values, [name]: text } }));
    // What the simulator said of it is of the value it was given.
    setProblems((now) =>
      Object.fromEntries(Object.entries(now).filter(([field]) => field !== `parameters.${name}`)),
    );
  }

  return (
    <Section heading={heading}>
      <p className="builder-note">
        The parameter sets of {model}, the crop model the rows grow: its published set, and those
        this simulator keeps.
      </p>
      <Field label="Parameter set" size="compact" className="builder-give-field">
        {(control) => (
          <select
            {...control}
            disabled={busy}
            value={chosen === null ? "" : setName(chosen)}
            onChange={(event) => {
              const picked = sets.find((each) => setName(each) === event.target.value);
              setChosen(
                picked === undefined ? null : { name: picked.name, version: picked.version },
              );
            }}
          >
            {sets.map((each) => (
              <option key={setName(each)} value={setName(each)}>
                {setName(each)}
                {each.published ? ", published" : ""}
              </option>
            ))}
          </select>
        )}
      </Field>
      {listedChosen !== undefined && (
        <p className="builder-note" data-testid="parameter-set-chosen">
          {listedChosen.published
            ? "Its model's published set"
            : listedChosen.based_on === null
              ? "Based on no set"
              : `Based on ${setName(listedChosen.based_on)}`}
          , made for {model} version {listedChosen.made_for}
          {listedChosen.cultivar === null ? "" : `, for ${listedChosen.cultivar}`}. Its digest is{" "}
          {listedChosen.digest}.
        </p>
      )}
      <div className="builder-actions">
        <Button
          size="compact"
          disabled={busy || base?.based_on == null}
          onClick={() => void compare()}
        >
          Compare with its base
        </Button>
        <Button size="compact" disabled={busy || base === null} onClick={() => void download()}>
          Download its file
        </Button>
      </div>
      {comparison !== null && <Comparison comparison={comparison} />}
      {base !== null && (
        <Fold
          className="builder-parameter-edit"
          summary={<span id={formHeading}>A new version, based on {setName(base)}</span>}
        >
          {/* The simulator checks what is given, and says by field what it refuses. */}
          <form
            className="builder-parameters"
            aria-labelledby={formHeading}
            noValidate
            onSubmit={(event) => void save(event)}
          >
            <p className="builder-note">
              Change a value within its range and say where it comes from. A set is saved as its
              name's next version, or is the version of its name that has the same numbers.
            </p>
            <Field
              label="Name"
              hint="Lower-case letters, digits and _, such as agc4_pretrial_2023."
              problem={problems.name}
              size="compact"
              className="builder-give-field"
            >
              {(control) => (
                <input
                  {...control}
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              )}
            </Field>
            <Field
              label="Cultivar"
              hint="The cultivar its values are for, if they are for one."
              problem={problems.cultivar}
              size="compact"
              className="builder-give-field"
            >
              {(control) => (
                <input
                  {...control}
                  value={form.cultivar}
                  onChange={(event) => setForm({ ...form, cultivar: event.target.value })}
                />
              )}
            </Field>
            <Field
              label="Description"
              problem={problems.description}
              size="compact"
              className="builder-give-field"
            >
              {(control) => (
                <input
                  {...control}
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                />
              )}
            </Field>
            {fields.map((field) => (
              <ParameterValue
                key={field.name}
                field={field}
                base={base}
                form={form}
                problems={problems}
                onValue={(text) => typed(field.name, text)}
                onWhy={(text) =>
                  setForm((now) => ({ ...now, why: { ...now.why, [field.name]: text } }))
                }
              />
            ))}
            <Button type="submit" size="compact" disabled={busy || madeFor === undefined}>
              Save this version
            </Button>
          </form>
        </Fold>
      )}
      {status !== "" && (
        <Notice kind="status" data-testid="parameter-set-status">
          {status}
        </Notice>
      )}
      {problem !== null && (
        <Notice kind="problem" data-testid="parameter-set-problem">
          {problem}
        </Notice>
      )}
    </Section>
  );
}

function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="builder-parameter-sets" aria-labelledby={heading}>
      <h2 id={heading}>Crop parameters</h2>
      {children}
    </section>
  );
}
