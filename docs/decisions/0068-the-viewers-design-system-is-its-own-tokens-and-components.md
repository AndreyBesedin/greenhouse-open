# 0068: The viewer's design system is its own tokens and components

**Status:** Proposed
**Date:** 2026-11-03

## Context

The viewer's look is one stylesheet of 2,395 lines, grown a feature at a time
(`greenhouse_sim/web/src/styles.css`, at commit `28701e05`; the audit, with how
each figure was counted, is in
[P19](../roadmap/p19-design-system.md#the-audit)):

- **Only colours are named,** after places (`--panel-*`, `--landing-*`,
  `--chart-*`) and not what they do. Sizes are written out: 14 font sizes, 13
  radii, 31 paddings and 17 gaps. Seven colours are written raw, 15 times, in
  `stroke`, `fill` and `border`, where the stylesheet's guard, which reads
  `color` and `background` only, does not look.
- **A control has no one definition.** Of 82 `<button>` in 33 files, 64 have
  no class and are drawn by the browser, most 21 px high; among the rest, four
  families repeat one box (`.home-button`, `.landing-link-button`,
  `.landing-button`, `.replay-button`). The 44 px target holds on the landing
  page and the replay, because those rules say so. It does not hold on the
  builder, whose first step's 20 controls are all under 24 px, nor on the viewer's
  panels.
- **A focus ring is written on two controls;** every other has the browser's.
  Nothing states a contrast or checks one.
- **A pixel cannot be held.** The 27 screenshot baselines are QA pages at a
  threshold that lets a small colour change through (decision 0014). None
  shows the landing page, the builder, the replay or a panel.

What the viewer needs is to organise what it has. The options weighed:

| Option | Adds, minified | Gives | Against it |
| --- | --- | --- | --- |
| Material UI 9.5 | 226.5 kB of script | every component, styled | its look, a new visual design; 22 times the room |
| Chakra UI 3.37 | 127.1 kB of script | the same | the same; 13 times the room |
| Mantine 9.7 | 124.5 kB of script, 248.4 kB of styles | the same | the same; its styles are nine times the viewer's |
| React Aria Components 1.22 | 98.4 kB of script | behaviour, no look | tokens and styles are still to be written |
| Radix dialog and slider | 59.3 kB of script | a dialog and a slider, no look | what `<dialog>` and `<input type="range">` give, and the viewer uses both |
| Our own tokens and components | 3.1 kB of script, 2.8 kB of styles (a prototype's) | what the audit shows is repeated | is ours to keep |

The viewer's scripts weigh 1,739.86 kB against a budget of 1,750 kB
(`src/bundleBudget.ts`), so 10.14 kB of room. The budget is raised when a weight
is meant, and has been, so the room alone would not decide this. It decides
with the rest: the styled libraries bring a look that is not the viewer's, and
the headless ones add no behaviour the viewer lacks at many times the room. The
largest weighs more than everything the viewer's scripts have gained since
2026-10-23 (154 kB).

## Decision

- **Own tokens and components, no UI library.** No runtime dependency is added
  for the viewer's controls. A later need that native elements and a small
  component cannot meet is a decision of its own.
- **Three layers,** each using only the one below: tokens (`src/design/tokens.css`);
  components (`src/design/`, classes prefixed `ds-`, restyled by no page); page
  layouts (each page's stylesheet beside it). A component is extracted when the
  audit shows it repeated, and not before.
- **Plain classes in stylesheets, not CSS modules.** One entry, `src/styles.css`,
  imports the others in an explicit order, which is the cascade's order. The
  existing naming guard already gives what modules would: each class owned by
  its feature, each used. Modules weigh 7.1 to 11.9 kB of the 10.14 kB of room,
  and hash the names that about 110 lines in 29 test files select by.
- **One theme mechanism, named for what it does.** `data-panels` becomes
  `data-theme` and `panelTheme.ts` becomes `design/theme.ts`; it covers every
  page, as it already does. Each colour token is defined once per theme.
- **The scene keeps its palette.** Three.js takes no CSS. The scene's colours
  stay in TypeScript, the same in either theme (#208), and a token is never read
  by the scene. A colour both show is held equal by a test.
- **Accessibility rules live in the system** and each has a check that fails:
  names by required props, contrast by a test over the tokens, targets measured
  in a browser, one focus ring, and a status always in words.
- **Drift is a failing test.** `styles.test.ts` is extended to refuse a raw
  colour or a raw size outside the tokens, with its exceptions named in the test.
- **The migration changes no pixel until it says so.** Proofs are merged before
  anything moves: a digest of the stylesheet with its tokens resolved, and
  screenshots of each page at no tolerance. A visual change is a pull request of
  its own, named, with its baselines drawn again by CI.

## Consequences

- **Easier:** a control is one component, a size one of few, and a colour says
  what it is for, so a page and a panel can no longer drift apart unnoticed; a
  contributor sees everything on one reference page.
- **Harder:** a class name is read by no bundler, so scoping stays a convention
  held by a test. A token costs bytes: the styles' budget rises from 29 kB to
  about 32 kB, measured in the step that crosses it.
- **Next:** [P19](../roadmap/p19-design-system.md), whose first step changes no
  style at all. The landing page's step follows the work in progress on
  `RunsDialog.tsx` and the new-run form.
- **Left as it is:** a look. The builder and the panels stay drawn by the browser
  until a named visual step says otherwise; P19 lists those steps, and which
  to take is decided one at a time.
- **Worth revisiting** if a control's behaviour outgrows a small component (a
  date range, a virtualised table), or if the viewer's scripts stop being held
  to a budget.
