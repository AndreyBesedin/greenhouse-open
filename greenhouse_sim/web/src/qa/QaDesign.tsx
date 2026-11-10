import { type CSSProperties, useEffect, useRef } from "react";

import { Button } from "../design/Button";
import type { ButtonSize, ButtonTone } from "../design/buttonClass";
import { Field } from "../design/Field";
import { Fold } from "../design/Fold";
import { IconButton } from "../design/IconButton";
import { LinkButton } from "../design/LinkButton";
import { Notice } from "../design/Notice";
import { StatusChip, type StatusTone } from "../design/StatusChip";
import { useFolds } from "../folds";
import { HomeIcon } from "../icons";

// Every token of `tokens.css`, which a browser test holds against that file.
const COLOURS = [
  "surface-page",
  "surface-panel",
  "surface-label",
  "surface-backdrop",
  "text",
  "text-soft",
  "text-muted",
  "border",
  "border-control",
  "action",
  "warn",
  "danger",
  "go",
  "mark",
  "chart-face",
  "chart-ring",
  "chart-neutral",
  "chart-strong",
  "chart-soft",
  "chart-off",
  "chart-faint",
  "chart-blue-text",
  "data-amber",
  "data-blue",
  "data-green",
  "data-navy",
  "data-orange",
  "data-red",
  "data-sky",
];
const FONTS = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl", "4xl"];
const RADII = ["sm", "md", "lg", "xl", "pill"];
const LENGTHS = [
  "space-1",
  "space-2",
  "space-3",
  "space-4",
  "space-5",
  "space-6",
  "space-7",
  "space-8",
  "space-9",
  "target",
  "target-compact",
  "focus-width",
  "focus-offset",
];

const TONES: readonly ButtonTone[] = ["plain", "primary", "danger", "go"];
const SIZES: readonly ButtonSize[] = ["target", "compact"];
const STATUS_TONES: readonly StatusTone[] = ["plain", "active", "problem"];

// Written here, not in a stylesheet, so that no page of the viewer's carries this
// one's rules in the styles' budget; its ground and text are `.ds-page`'s.
const PAGE: CSSProperties = { padding: "var(--space-5)", fontSize: "var(--font-sm)" };
const ROW: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: "var(--space-3) var(--space-5)",
  margin: "var(--space-3) 0",
  padding: 0,
  listStyle: "none",
};
// Fields side by side, each from the top, as they differ in height.
const FIELD_ROW: CSSProperties = { ...ROW, alignItems: "start" };
const TOKEN: CSSProperties = { display: "flex", alignItems: "center", gap: "var(--space-2)" };
const SWATCH: CSSProperties = {
  width: "var(--space-7)",
  height: "var(--space-7)",
  border: "1px solid var(--border)",
  background: "var(--text-muted)",
};
const HEADING: CSSProperties = { margin: "var(--space-4) 0", fontSize: "var(--font-md)" };

function Token({ name, shown }: { name: string; shown: CSSProperties }) {
  return (
    <li style={TOKEN}>
      <span style={{ ...SWATCH, ...shown }} />
      --{name}
    </li>
  );
}

function ButtonsOf({ tone, size }: { tone: ButtonTone; size: ButtonSize }) {
  const look = { tone, size };
  const name = `${tone} ${size}`;
  return (
    <div style={ROW}>
      <Button {...look}>{name}</Button>
      <Button {...look} disabled>
        {name}, disabled
      </Button>
      <LinkButton {...look} href="#link">
        {name}, a link
      </LinkButton>
      <IconButton {...look} label={`${name}, an icon`}>
        <HomeIcon />
      </IconButton>
      <IconButton {...look} label={`${name}, an icon, disabled`} disabled>
        <HomeIcon />
      </IconButton>
    </div>
  );
}

/**
 * Each token and each component in each tone, size and state, `/qa/design`:
 * what CI can draw of them with no simulator and no fixture, in each theme.
 */
export function QaDesign() {
  const focused = useRef<HTMLButtonElement>(null);
  useEffect(() => focused.current?.focus(), []);
  const fold = useFolds<"open" | "folded">(["open"]);
  return (
    <main className="ds-page" style={PAGE}>
      <h1 style={HEADING}>Design system</h1>
      <h2 style={HEADING}>Colours</h2>
      <ul style={ROW}>
        {COLOURS.map((name) => (
          <Token key={name} name={name} shown={{ background: `var(--${name})` }} />
        ))}
        <li style={TOKEN}>
          <progress value={1} max={2} />
          --scheme
        </li>
      </ul>
      <h2 style={HEADING}>Type</h2>
      <ul style={ROW}>
        {FONTS.map((name) => (
          <li key={name} style={{ fontSize: `var(--font-${name})` }}>
            --font-{name}
          </li>
        ))}
      </ul>
      <h2 style={HEADING}>Radii</h2>
      <ul style={ROW}>
        {RADII.map((name) => (
          <Token
            key={name}
            name={`radius-${name}`}
            shown={{ borderRadius: `var(--radius-${name})` }}
          />
        ))}
      </ul>
      <h2 style={HEADING}>Lengths</h2>
      <ul style={ROW}>
        {LENGTHS.map((name) => (
          <Token key={name} name={name} shown={{ width: `var(--${name})` }} />
        ))}
      </ul>
      <h2 style={HEADING}>Buttons</h2>
      <div style={ROW}>
        <Button ref={focused}>focused</Button>
      </div>
      {SIZES.flatMap((size) =>
        TONES.map((tone) => <ButtonsOf key={`${tone}-${size}`} tone={tone} size={size} />),
      )}
      <h2 style={HEADING}>Fields</h2>
      <div style={FIELD_ROW}>
        <Field label="a field">{(control) => <input {...control} />}</Field>
        <Field label="a field, with a hint" hint="what it takes">
          {(control) => <input {...control} defaultValue="a value" />}
        </Field>
        <Field label="a field, with a problem" hint="what it takes" problem="why it is refused">
          {(control) => <input {...control} defaultValue="a value refused" />}
        </Field>
        <Field label="a field, disabled">
          {(control) => <input {...control} defaultValue="a value" disabled />}
        </Field>
        <Field label="a choice">
          {(control) => (
            <select {...control}>
              <option>an option</option>
            </select>
          )}
        </Field>
      </div>
      <div style={FIELD_ROW}>
        <Field label="a compact field" size="compact">
          {(control) => <input {...control} />}
        </Field>
        <Field label="a compact choice" size="compact">
          {(control) => (
            <select {...control}>
              <option>an option</option>
            </select>
          )}
        </Field>
      </div>
      <h2 style={HEADING}>Status chips</h2>
      <div style={ROW}>
        {STATUS_TONES.map((tone) => (
          <StatusChip key={tone} tone={tone}>
            {tone}
          </StatusChip>
        ))}
        <StatusChip tone="problem" note="what it means">
          problem, with a note
        </StatusChip>
      </div>
      <h2 style={HEADING}>Notices</h2>
      <Notice kind="status">a status</Notice>
      <Notice kind="problem">a problem</Notice>
      <h2 style={HEADING}>Folds</h2>
      <Fold summary="open" {...fold("open")}>
        <p>what it holds</p>
      </Fold>
      <Fold summary="folded" {...fold("folded")}>
        <p>what it holds, folded</p>
      </Fold>
    </main>
  );
}
