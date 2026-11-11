# P19: The viewer's design system

**Status:** done: P19.1 to P19.12, its final QA recorded; what it left is in
[future work](../future-work.md#the-design-system-after-p19). The design below, with decision
[0068](../../decisions/0068-the-viewers-design-system-is-its-own-tokens-and-components.md).
Part of the [simulator roadmap](../README.md).

## Goal

Every colour and size in the viewer has a name that says what it is for, every
repeated control has one definition, and a test refuses what departs from them.
This organises what exists. It adds no new look, and it does not touch how the
scene is drawn.

## The audit

**Method.** At commit `28701e05`, in `greenhouse_sim/web/src`. Stylesheet figures
are from `styles.css`, comments removed: values compared as written, per
declaration, and outside the two `:root` blocks unless said. Source figures are
from the 217 handwritten `.ts` and `.tsx` files (no tests, no `generated/`),
with each opening tag read up to its own `>`. Sizes of controls were measured
in Chromium at 1280 by 800 with every fold open, against the running simulator.
Contrast is WCAG's ratio; a translucent panel is composed over white and over
black, and the lower is given. Weights are `vite build`'s, on a copy of the
viewer; the prototypes were not run, only weighed.

**The stylesheet:** 2,395 lines, 358 rules, 242 classes, 1,067 declarations.

| What | Found | Where it stands |
| --- | --- | --- |
| Hex colours | 35 distinct: 29 in `:root`, 7 outside, used 15 times (one is in both) | A bare search finds 49: 14 are issue numbers in comments |
| `rgb()` colours | 6, all in `:root` | |
| Custom properties | 22, 20 redefined in the light theme, all on `:root` | Named by place: `--panel-*` 9, `--chart-*` 8, `--landing-*` 2, `--replay-*` 2, `--label-*` 1 |
| Font sizes | 14 distinct, 41 uses | 13 px has 15 of them; each page sets its own base: panels 13, builder 14, replay 14, landing 15 |
| Radii | 13 distinct, 29 uses | 8, 6 and 4 px have 15 of them |
| Paddings, gaps | 31 and 17 distinct, 63 and 60 uses | |
| Font weights | 1, `600` | Family once, `z-index` once: neither needs a token |
| Motion | No `transition`, `animation` or `@keyframes`; no `prefers-reduced-motion` | Nothing to reduce today |
| Media queries | 1 | |
| Classes by first word | `landing` 41, `replay` 27, `builder` 25, `timeline` 10, `panel` 6 | As selector occurrences: 62, 34, 40, 10, 30 |

**The raw colours** the guard misses, because it reads `color` and `background`
alone: `#c0392b` (4 uses), `#2b7bb9` (4), `#ff8c1a` (2), `#0072b2` (2), `#2e86c1`,
`#e6a800`, `#2e8b57`, in `stroke`, `fill` and one `border`: chart lines, which
are the same in both themes. Two also stand in TypeScript: `WIND_COLOR` and
`SUN_COLOR` (`weather/weather.ts`), so a panel and the scene can drift apart.

**The sources:**

| Element | Count | How it is made today |
| --- | --- | --- |
| `<button>` | 82 in 33 files | 64 with no class, drawn by the browser (a contextual rule gives some a margin or a height); the rest carry 13 classes among them |
| `<a>` styled as a button | 9 of 16 | `.landing-link-button` 7, `.home-button`, `.replay-back` |
| Rules naming a button | 10 | Plus contextual ones such as `.builder-share button` |
| `<label>`, `<input>`, `<select>` | 55, 54, 20 | 49 inputs, all selects and 26 labels with no class; `.landing-field`, `.builder-field`, `.builder-give-field` |
| `<details>` | 19 in 14 files | 8 fold classes, listed together in three rules; `folds.ts` keeps their state |
| `role="alert"`, `role="status"` | 29 in 21 files, 6 in 4 | 17 are a bare `<p role="alert">`, in the text's colour |
| `<input type="range">` | 8 in 6 files | Native; the replay's timeline is one `role="slider"` of its own |
| `<dialog>` | 1 | `RunsDialog.tsx` |
| Cards | 4 looks | `.landing-card` (radius 12, padding 24), `PanelCard` (4 uses in one file, title on its outline), `.builder-chosen` (radius 4, padding 8), the panels over the view (radius 6, one selector list) |
| Status chip | 1 | `StatusChip` in `landing/RunParts.tsx`, in words |
| `<svg>` | 14 in 10 files | 5 icons in 2 files (`HomeButton`, `ReplayTransport`), 9 charts in 8 |
| `style=` | 13 in 9 files | All computed; see below |
| Colour literals in TypeScript | 55 in 16 files, 47 distinct | The scene's palette; see below |

**Inline styles, all 13 computed:** a position or size from data (`ReplayTimeline`
4, `ClimateSchedule`, `CameraView`, the moved `Hud`) or a colour that is the
scene's or a scale's, in a legend (`CategoryLegend`, `CfdLegend`, `ScalarLegend`,
`FieldLegend`, `SeenInTheView`, `CameraView`). None holds a design value, and
none needs to go.

**Controls' heights,** the same in both themes:

| Page | Controls | Under 44 px | Under 24 px | Typical |
| --- | --- | --- | --- | --- |
| Landing | 5 | 0 | 0 | 44, its search 48 |
| Builder, first step | 20 | 20 | 20 | inputs and buttons 21, selects 19 |
| Viewer, reference greenhouse, folds open | 63 | 60 | 59 | buttons 21, selects 19, summaries 16, ranges 16, checkboxes 13 |

The replay's own controls are 44 px by their rules, and were not measured here.
One browser test holds a target today: `e2e/home.spec.ts`, the Home link.

**Contrast, at the worst backdrop:**

| Tokens today | Dark | Light | Against |
| --- | --- | --- | --- |
| `--panel-text`, `-muted-strong`, `-muted`, `-warn`, `-link` | 11.00, 8.12, 6.19, 7.66, 6.64 | 15.97, 7.41, 5.67, 5.88, 4.63 | 4.5, passes |
| `--panel-accent` | 4.81 | 4.63 | 4.5, passes |
| `--chart-soft`, as text in a key | 4.36 | 2.64 | 4.5, fails |
| `--panel-rule`, the only outline of every bordered button | 1.49 | 1.22 | 3, if it is what identifies the control; the button's words do |
| Chart lines, the same in both themes | `#c0392b` 2.46, `#0072b2` 2.58, `#2b7bb9` 2.96 | `#e6a800` 1.60, `#ff8c1a` 1.77 | 3, fails |

**Tests that would feel a change of class name:** about 110 lines in 29 test
files select by class, 28 of them in `e2e/builder.spec.ts`.

**Screenshots:** 27 baselines, all of QA pages, at `threshold: 0.2` and 100
pixels' tolerance (`playwright.visual.config.ts`), which a small change of a
caption's colour can pass. Of the stylesheet they see the captions, the legends
and the labels over the scene, in the light theme (`main.tsx` sets it for QA
pages). They see no landing page, builder, replay or panel.

**Theme.** There are not two mechanisms: `panelTheme.ts` writes `data-panels` on
the document, and the stylesheet's second `:root` block reads it. What is
scattered is around it: the name says *panels* though it colours every page; the
control is only in the info panel (`InfoPanel.tsx`), so the landing page and the
builder only read the stored choice (`main.tsx`); and `color-scheme:
var(--panel-scheme)` is written in five rules. The scene does not follow it, by
design (#208).

## Why not a library, or modules

Each weighed the same way: a button, a dialog, a slider, a text field and a chip
or their nearest, in an empty React page, with what React alone weighs (219.2 kB)
taken away.

| | Scripts added | Styles added |
| --- | --- | --- |
| Material UI 9.5 | 226.5 kB | in its scripts |
| Chakra UI 3.37 | 127.1 kB | in its scripts |
| Mantine 9.7 | 124.5 kB | 248.4 kB |
| React Aria Components 1.22 | 98.4 kB | none, nor a look |
| Radix dialog and slider | 59.3 kB | none, nor a look |
| Prototype of the seven components below | 1.36 kB | moved, not added |
| Its reference page | 1.71 kB | |

The viewer: 1,739.86 kB of scripts against 1,750, 28.40 kB of styles against 29.

CSS modules, the viewer's 242 classes in one module and its 330 static
`className` sites reading it (16 dynamic ones left):

| | Scripts | Styles | Against the budget |
| --- | --- | --- | --- |
| Plain classes, today | 1,739.86 kB | 28.40 kB | |
| Modules, Vite's default names | + 11.89 kB | + 5.42 kB | 1.75 kB over |
| Modules, 5-character names | + 7.05 kB | − 3.66 kB | 3.09 kB left |

A module's map of names has to ship as script. Short names repay most of the
total, but take 70% of the room in scripts, leave a page's classes unreadable,
and hash what the tests select by. What modules would add is scope, and the
naming guard already holds that each class has an owner and a use. So: plain
classes.

## Design

### Tokens

In `src/design/tokens.css`, on `:root`, the only place a custom property is
defined. A scale is what the stylesheet mostly uses already, so that the first
steps replace values and do not change them.

**Colour, by role.**

| Token | Is | Today | Dark | Light |
| --- | --- | --- | --- | --- |
| `--surface-page` | a page's ground | `--landing-bg` | `#0b1220` | `#f4f6f3` |
| `--surface-panel` | a panel, a card, a header | `--panel-bg` | `rgb(17 24 39 / 90%)` | `rgb(255 255 255 / 88%)` |
| `--surface-label` | a label over the scene | `--label-bg` | `rgb(17 24 39 / 85%)` | `rgb(255 255 255 / 85%)` |
| `--surface-backdrop` | behind a dialog | `--landing-backdrop` | `rgb(0 0 0 / 60%)` | `rgb(20 30 25 / 50%)` |
| `--text` | text | `--panel-text` | `#e5e9f0` | `#000000` |
| `--text-soft` | secondary text | `--panel-muted-strong` | `#c3cad6` | `#444444` |
| `--text-muted` | notes | `--panel-muted` | `#a7b1c2` | `#555555` |
| `--border` | a rule, an outline | `--panel-rule` | `#3d4a5f` | `#cccccc` |
| `--action` | a link, a primary control, what is computed | `--panel-link` | `#8cb8ff` | `#1f5fbf` |
| `--warn` | a problem | `--panel-warn` | `#ffb380` | `#8a3b12` |
| `--mark` | a stripe under the pointer, a dashed QA outline | `--panel-accent` | `#e277b5` | `#aa3377` |
| `--scheme` | the browser's own controls | `--panel-scheme` | `dark` | `light` |
| `--chart-*` | a chart's face, ring and neutral lines | as named: `face`, `ring`, `neutral`, `strong`, `soft`, `off`, `faint`, `blue-text` | as today | as today |
| `--data-*` | a chart's coloured lines, the same in both themes, named by hue, since what red means is each chart's | the raw colours above: `red`, `blue`, `sky`, `navy`, `amber`, `orange`, `green` | | |


**Sizes.**

| Group | Tokens | px |
| --- | --- | --- |
| Type | `--font-xs`, `sm`, `md`, `lg`, `xl`, `2xl`, `3xl`, `4xl` | 12, 13, 14, 15, 16, 18, 22, 28 |
| Spacing | `--space-1` to `--space-9` | 2, 4, 6, 8, 12, 16, 24, 32, 64 |
| Radii | `--radius-sm`, `md`, `lg`, `xl`, `pill` | 4, 6, 8, 12, 999 |
| Target | `--target`, `--target-compact` | 44, 24 |
| Focus | `--focus-width`, `--focus-offset` | 3, 2, in `--action` |

On a copy, these replace 288 of the 333 such values written in pixels: 224 of
254 spacings, 35 of 38 font sizes, 18 of 27 radii, 11 of 14 minimum sizes. Of
the other 45, 5 are hairlines and offsets (below), and 40 are off the scale (10,
14, 18 and 20 px of spacing; radii of 1, 2, 3, 7 and 14): these stay as they are,
listed, until a visual step moves them. The stylesheet then weighs 31.16 kB,
2.76 kB more (0.25 kB gzipped), over the budget of 29 kB: the budget goes to
32 kB in the step that crosses it.

**Motion:** none exists, so no token does. The first `transition` or `animation`
adds its token, and a `prefers-reduced-motion: reduce` block in `tokens.css`
that sets it to no time; a test requires the block once any `--motion-*` exists.

### Components

In `src/design/`, one file each, their rules in `src/design/components.css`. Their
classes begin `ds-`, added to the naming guard as one first word; `field` and
`timeline` are already features' words. Only `src/design/` may write a `.ds-`
selector, so that no page restyles a component. A page places one (margin, grid
area) through its own wrapper or its own class beside it.

| Component | Why | Takes |
| --- | --- | --- |
| `Button`, `LinkButton` | 82 buttons and 9 links, in four families repeating one box | `tone` (plain, primary, danger), `size` (`target` 44 px by default, `compact`) |
| `IconButton` | the replay's three transport buttons, and whatever comes | a required `label`, its name; a `src/icons/` icon inside |
| `Field` | a label, its control, a note or a problem: `.landing-field`, `.builder-field`, `.builder-give-field` | a required `label`, `hint`, `problem`, the control |
| `StatusChip` | exists, moves from `landing/RunParts.tsx` | a `tone`, and its words as a required string |
| `Notice` | 35 alerts and statuses | `problem` or `status`, which sets the role |
| `Fold` | 19 `<details>`, 8 of their classes listed in three rules | its summary; `folds.ts` keeps its state |

**Not extracted, on the same audit:**

- **`Dialog`:** one `<dialog>`, whose behaviour is the browser's. It is extracted
  by the pull request that adds a second, as the new-run form may.
- **`Card`:** four looks that share neither radius nor padding, and no behaviour.
  `PanelCard` stays; the others stay classes.
- **`Slider`:** eight native ranges, styled by a class on two of them, and one
  timeline whose pointer logic is its own.
- **Charts and tables:** 9 charts, 4 tables, each with its own marks. A chart
  helper is not this project's.
- **Icons:** `src/icons/`, as #472 adds it, is the one way to draw one. It stays
  where it is, and the replay's four inline ones move into it. Its comment that
  an icon alone "is not made with this" gives way to `IconButton`, whose `label`
  names the button while its icon stays decoration.

### Page layouts

Each page's own stylesheet beside it, holding its grid and places, using tokens
and components: no layout component. `.ds-page`, one class, gives a page its
ground, text and scheme, which `.landing`, `.builder-side` and `.replay` each
write out today. The panels stay in one sheet until their step.

### Files

```
src/styles.css            imports only, in the cascade's order: main.tsx's one import
src/design/tokens.css     every custom property, in both themes
src/design/base.css       html, body, the focus ring, .visually-hidden
src/design/components.css every .ds- rule
src/design/*.tsx          the components, and theme.ts
src/icons/                as #472 adds it
src/landing/landing.css, src/builder/builder.css, src/replay/replay.css
src/viewer.css            the panels: what is left of today's stylesheet, 1,522 lines
src/qa/QaDesign.tsx       the reference page
```

Components do not import their CSS: the order of imports through the module graph
would become the cascade's. Tried on a copy, this cut through `@import` builds
to the same stylesheet, byte for byte. `@layer` is not used: it would change how
today's contested rules resolve, and the order and the guard do its work.

### Light and dark

One mechanism: `src/design/theme.ts` (once `panelTheme.ts`) writes `data-theme`
on the document (once `data-panels`), and `tokens.css` holds each colour once
per theme. The key a person's choice is stored under, `greenhouse-sim.panels`,
does not change, so that nobody's choice is lost. Dark stays the default, and QA
pages stay light, as `main.tsx` sets them, so that their baselines stay.

**The scene needs no token.** Three.js takes colours as values, not CSS, and
`src/` reads no custom property from a script. The scene's background, materials,
overlays and colour scales (55 literals in 16 files) stay in TypeScript, the same
in both themes (#208). The flow is one way: a legend shows a scale's colour through
`style`. Where a chart in a panel and the scene show one thing, wind and sun, a
test holds `--data-blue` equal to `WIND_COLOR` and `--data-amber` to `SUN_COLOR`.

### Accessibility

| Rule | Today | Held by |
| --- | --- | --- |
| **Every control has a name** | 110 `aria-label`s by hand; icons `aria-hidden` (#472) | `label` is a required prop of `IconButton` and `Field`; a browser test asks each control on the reference page for its accessible name |
| **Contrast:** text 4.5:1 on each surface it sits on; control outlines and chart lines 3:1 | Not stated, not checked; failures above | A test in `styles.test.ts` reads `tokens.css` and computes the declared pairs in both themes, translucent surfaces over white and black; today's failures are listed in it and removed by their visual step |
| **Target size:** `size="target"` is 44 px; `compact` is for dense panels | 44 on landing and replay only | A browser test measures every control on the reference page; `home.spec.ts` stays |
| **Focus:** one `:focus-visible` ring in `base.css` | On 2 controls; the browser's elsewhere | The guard refuses `outline: none` and any other `:focus-visible` rule; the reference page's baseline draws one focused |
| **A status is never a colour alone** | `StatusChip` in words | Its words are a required string, and `Notice` holds text; the runs and findings use these |
| **Reduced motion** | Nothing moves | The test above |

`axe-core` is left out: a development dependency for what the types and these
tests check, to weigh again if a page's structure starts to slip through.

### The guard

`styles.test.ts` is extended and reads every stylesheet through the entry. Each
rule has a test that it can fail, as the file's rules do today.

- **Colours:** no hex, colour function or colour name in any declaration, not just
  `color` and `background`, outside `tokens.css`.
- **Custom properties** are defined on `:root` in `tokens.css` only.
- **Sizes:** `font-size`, `border-radius`, `gap`, `padding*`, `margin*`,
  `min-height`, `min-width` and `outline*` are a token, or an allowed value.
- **Sources:** `style=` holds no literal colour or pixel size, and a colour literal
  stands only in the files listed.
- **`.ds-`** selectors stand only in `src/design/`.

Its exceptions, named in the test:

- `0`, `auto`, `inherit`, `none`, `transparent`, `currentColor`, percentages;
- `em` values, which follow their text (7 today, such as `.panel-card-title`'s);
- 1 px hairlines and negative offsets that centre a mark (5);
- a chart's geometry: `stroke-width`, `stroke-dasharray`, and text in a viewBox's
  units (`.wind-compass-north`);
- a place or size in a layout, unheld: `width`, `height`, `top`, `left`, `inset`,
  `max-width`, a border's width;
- the pattern of the replay's track;
- the 13 computed `style=`, which hold no literal;
- the palette's files in TypeScript, listed with what each draws;
- `OFF_SCALE`, the values above by selector and property. It can only shrink: an
  entry no longer in the stylesheet fails too.

### The reference page

**Yes: `/qa/design`,** `src/qa/QaDesign.tsx`, one more QA page, unlinked, taking
its theme from its address. It shows each token and each component in each tone,
size and state: disabled, a problem, one focused, every status.

It earns its 1.71 kB because it is what CI can draw of a component with no
simulator and no fixture: two baselines, one per theme, show every state a page
reaches only with data. It is also where a browser test measures targets and
names, and where a contributor looks first. It is not a second documentation, and
no prose is kept on it. Storybook would weigh nothing in the bundle, but it is a
second toolchain and build for what one page does, and decision 0014's pinned
screenshots would still have to reach it.

### How the first steps are held to no pixel

Two proofs, merged before anything moves, so that a step cannot change the proof
it is judged by.

1. **The resolved digest.** A test replaces every `var()` with its value, for each
   theme, drops the `:root` blocks and comments, and compares the digest of what
   is left, in the entry's order, with a constant. With custom properties only on
   `:root`, a substitution is exactly what the browser computes, and equal text in
   equal order is an equal cascade. A token step's diff leaves the constant alone.
   Tried on a copy: the 288 values, written as tokens, resolve to today's stylesheet
   byte for byte. A change of the stylesheet meanwhile updates the constant in its
   own diff. The test goes when selectors start to move (P19.8; P19.6's row says why
   not sooner).
2. **Page baselines at no tolerance.** `e2e/visual/pages.spec.ts`, 10 new images
   drawn by CI: the landing page, the runs dialog, the builder's first step, the
   replay and the viewer on `/view?scene=example` with its folds open, each dark
   and light, with `threshold: 0` and `maxDiffPixels: 0`. What the stylesheet does
   not draw is left out (`e2e/visual/pages.css`): the canvas and the labels over
   it, the viewer inside a replay, the HUD's measurements of the machine, and the
   commit the viewer was built from. The visual job has no simulator, so the page's
   few requests (`/api/scenarios`, `/api/runs`, `/api/drafts`, a position) are
   answered in `e2e/visual/pageAnswers.ts`, typed by the simulator's contracts, so
   that a change of one fails the type check before the baselines' build. A question
   it does not know fails the test. The date, time zone and locale are fixed. A
   page's image is under 100 kB. They take over from the digest for the component
   steps, whose selectors change and whose pixels must not. Their spec holds them to
   this: a colour one level away, or a padding, radius or font size one pixel away,
   fails its comparison, in every run of the job.

**While they stand.** A change that means to change a look writes the digests
the test prints, in its own diff, until they go. A change of a page's
look or words takes that page's new images from CI's `visual-results`, as any
baseline does (decision 0014).

**What is disturbed.** Tokens, the split and the components disturb no baseline:
if one moves, the step is wrong, but for a control moved to `compact`, a named
visual change. Of the 27 QA baselines, only a visual step that
reaches the captions, the legends or the scene's labels can move any: the caption's
values (13 px, radius 6, padding 4 and 8) are on the scale, while the legend's
swatches (radius 2), the label's radius (3) and `#ff8c1a` are the ones to watch.
Each visual step redraws what it moves in CI, as decision 0014 says.

## Steps

Each under 500 lines by the risk gate's count, where a moved line counts twice, so
a large cut goes in parts. A step that says *neutral* passes with no baseline and
no digest changed.

| Step | Scope | Proof | Status |
| --- | --- | --- | --- |
| P19.1 | The proofs: the resolved digest, page baselines and their answers. No style changes. The job is run twice, to show the no-tolerance images are stable. | adds them | Done: `styles.test.ts` (`RESOLVED_DIGESTS`), `e2e/visual/pages.spec.ts` and 10 images drawn by CI |
| P19.2 | `design/tokens.css` and `base.css` cut out behind `styles.css`'s imports; the 7 raw colours become `--data-*`, with the test against `WIND_COLOR` and `SUN_COLOR`; the guard on colours everywhere. | neutral | Done: the digests did not move. `--replay-track` and `--replay-hatch`, each used once, went back into their rules. `base.css` holds `html`, `body` and `#root`; `.visually-hidden` stays where it stands until selectors may move (P19.6), since moving it changes the order the digest holds |
| P19.3 | Colour tokens take their role names. | neutral | Done: the digests did not move, and a test refuses a colour token not named for a role. `--chart-*` keep their names, as the design has it |
| P19.4 | Type, radii and `--target`; the guard on them, with `OFF_SCALE`; the styles' budget raised. | neutral | Done: the digests did not move. 64 values became tokens: 35 font sizes, 18 radii, 11 minimum sizes. `OFF_SCALE` holds 13 declarations, and the compass's text in its viewBox's units stands beside it. The styles went from 28.20 to 29.11 kB; on a copy with spacing's tokens as well, 31.66 kB, so the budget went to 32 kB, as this step was settled to |
| P19.5 | Spacing, and the guard on it. Theme: `data-theme` and `design/theme.ts`. | neutral | Done: the digests did not move. 227 values in 189 declarations became `--space-*`. `OFF_SCALE` took 23 more declarations, at 10, 14, 18 and 20 px, and `HAIRLINES_AND_OFFSETS` names 5. `--focus-width` and `--focus-offset` hold the two focus rings and the guard holds `outline*`, the chosen option's outline in `OFF_SCALE`. `design/theme.ts` writes `data-theme`; the key a choice is stored under, the default and the QA pages' light theme did not change. The styles weigh 32.72 kB: spacing and the focus tokens, and the columns of a list of runs, which landed beside them. So the budget went to 34 kB, with room for P19.6's `.ds-` rules |
| P19.6 | `Button`, `LinkButton`, `IconButton`, `.ds-` rules and the guard on them; the reference page, its two baselines and its browser test; the contrast test with today's failures listed. The digest test goes, if the rest holds what it held. | neutral: nothing yet uses them | Done: the digests did not move, as they now leave out `design/components.css`, and they stay. A raw value fails the guards, and a token moved by the least fails the reference page's baselines, each token's draw being held by `e2e/design.spec.ts`; but 206 of the stylesheet's 370 rules, at `c0262394`, match nothing on the pages the no-tolerance baselines draw, so that a token swapped for another, or a property off the scales changed, in one of those fails only the digest. `--target-compact` (24 px) is new, as `OFF_SCALE` may not grow. `FOCUS_RINGS` names the four rings there are until P19.12, and a page's own `:focus-visible` fails. `CONTRAST_FAILURES` lists 18 pairs by name: in the audit's light `--chart-soft`, 2.64 is `--chart-off`'s; its own is 2.70. The page's own rules and ground are written in `QaDesign.tsx`, so that the styles gain only the `.ds-` rules, 0.79 kB. The pages having grown to 33.88 kB, the budget went to 34.7 kB, the least that holds them: the styles weigh 34.67 kB. The scripts weigh 1,764.30 kB against 1,765, the page 3.51 kB of them. `.visually-hidden` moves with the first cut of a stylesheet, P19.8 |
| P19.7 | `Field`, `StatusChip`, `Notice`, `Fold`, on the reference page; `.ds-page` moved to a stylesheet; the styles' budget to 36 kB. | neutral | Done: the digests did not move, and of the page baselines only the reference page's two were drawn again, with the new components on them, at 119 and 117 kB: over the 100 kB a page's image was to stay under, as the runs dialog's two already are; the landing page's and the runs dialog's, which show a chip in every state, did not move. The landing page's chips carry `landing-status` beside `ds-status-chip`, whose rules come later in the cascade and set every property the component's do, so that the page draws its own until P19.8 moves them: the component's sides are `--space-5`, the page's the 10 px `OFF_SCALE` holds. `RunStatus` maps a run to the chip's words and tone. `Field` gives its control its id, its description and whether it is invalid, and draws no control: a page's stays the page's, as `Fold`'s line stays the browser's, so that the reference page's browser test names them and does not measure their targets. `.ds-page` leaves `color-scheme` to `html`'s rule, which it inherits. The styles went from 35.16 to 35.93 kB, and their budget to 36 kB; the scripts weigh 1,743.71 kB against 1,765. The replay's header still writes `landing-status` for its chip, for P19.10. Not delivered: a target for a field's control or a fold's line, which stay the browser's size until P19.9 and P19.11 move them to `compact` |
| P19.8 | The digest goes, its rules starting to move. The landing page: its stylesheet moved in two parts, then its controls moved to components. **After the changes in progress to `RunsDialog.tsx` and the new-run form have merged,** since they touch the same lines. | its stylesheet neutral; the controls name what moves | Done, in four pull requests, with P22.7 in a fifth. **The digest goes:** `RESOLVED_DIGESTS` and the tests of what it saw left `styles.test.ts`; the tokens' resolution stays for the guards that every token used is defined and that custom properties stand on `:root` alone. A page's own `font-weight` is now held by nothing, as open question 2 said. **Its stylesheet, neutral, in two cuts:** `landing/landing.css` holds the landing page's rules, imported after the components' and before the builder's: first the start page's own (302 lines), then the runs dialog's and what a list's rows share (258). Each cut moved a block from the front of what was left, so the landing rules kept their order among themselves. `.visually-hidden` moved to `design/base.css`. Every element's computed style, pseudo-elements and box on the start page, the runs dialog, the replay, the builder, the viewer and the reference page, in both themes, at 1280 and 720 px wide, in ten states (a search open and one matching nothing, a *Delete* asking, a *Stop*, a start and an upload refused, days refused), 5,671,732 values, was what it was after each cut; a gap moved by 1 px showed 5,030. The page stylesheets' guard holds the landing page's rules too. **Its controls, a named visual change:** every button and link drawn as one is `Button` or `LinkButton`, its sides 12 px (`--space-5`) where they were 18, at least 44 px wide, with no ground of its own where it had the page's; *Contribute*'s icon is 6 px from its word where it was 8; a run's chip is `StatusChip` alone, its sides from the 10 px of `OFF_SCALE` to `--space-5`, as P19.7's row said; the search is a `Field`, drawn as before; problems are `Notice`, a row's refusal in `--warn` on the start page as in the dialog. The dialog's *Close*, focused as it opens, wears the tokens' ring. A field's typed text no longer takes `Field`'s 600. Moved: the start page's and the runs dialog's baselines, both themes, twice (the second time for P22.7). The styles went from 35.76 to 34.95 kB, within their 36.1 kB budget, which did not change; the scripts weigh 1,719.95 kB. Not delivered: the replay's header still draws its chip with `.landing-status`, kept in `landing/landing.css` for P19.10; `Fold` and `IconButton`, as the page has no fold and no button that is an icon alone; and a tooltip of the design system's, as there is none: the page's buttons take `title`, as the replay's do |
| P19.9 | The builder: its stylesheet, then its controls. Moving them to `compact` is a named visual change and not neutral: they go from the browser's drawing at 21 px to the tokens' at 24. Selectors `e2e/builder.spec.ts` reads change with it, to roles where they can. With it, from [P12's QA](p12-setup-builder.md#the-first-days-check): the house form's labels *Origin Position X* and *Origin X* say what tells them apart, and the house form and palette are walked by keyboard alone; and from the [QA of 2026-11-04](qa-2026-11-04.md#where-each-went), the run step's form laid out at 720 px high. | its stylesheet neutral; `compact` names what moves | Done, in five pull requests. **Its stylesheet, neutral:** `builder/builder.css` holds the builder's rules, imported after the components' and so before the viewer's. The order changed, so the digests moved, and nothing the builder draws did: every element's computed style on the builder, in both themes, at 1280 and 720 px wide, in seven of its states, 4,293,848 values, was what it was, and its two baselines did not move. A test keeps a page's rules in its own stylesheet. **Its controls, a named visual change:** every button is `Button`, `compact`, 24 px each way where the browser drew 21 px tall, but the three ways out, which keep their 44 px target from the component; every input and select is a `Field`'s control, `compact`, 24 px where the browser drew 21 (a select 19). `Field` takes a `size`, its control's least height, 44 px by default, which the reference page shows and its browser test measures. The fields' labels take `Field`'s type, 13 px at 600 in `--text-soft`, where the builder's were 14 px in `--text`, and the copy's refused identifier is `Field`'s problem, in `--warn`. Moved: the builder's two page baselines, twice, and the reference page's two. `e2e/builder.spec.ts` finds the forms and sections by role and name, and measures every control on the builder's side. **The QAs' items:** the house's origin and its rows' are titled by what each places, *House's corner in the world, x* and *First row's first plant, x*; a browser test walks the house form and the palette by keyboard alone; the run step's fields stand in a wrapped row, each as wide as the browser draws it, its weathers in words (*its own*, *cold spring day*), held at 1280 by 720. The styles went from 35.93 to 35.97 kB, their budget to 36.1 kB for `Field`'s rules before the builder's shrank; the scripts weigh 1,749.15 kB. Not delivered: the boxes to tick, which stay the browser's 13 px; the house form's and the copy's two columns keep `9em`, which now reads `Field`'s 13 px, 117 px where it was 126; and CI's container draws 600 as it draws normal, so the baselines do not show the labels' weight |
| P19.10 | The replay: its stylesheet, its transport to `IconButton`, its four icons to `src/icons/`. | its stylesheet neutral; the controls and the chip name what moves | Done, in two pull requests, with P22.9 in a third. **Its stylesheet, neutral:** `replay/replay.css` holds the replay's rules, imported after the builder's and before the viewer's; `.viewer-embedded` stays in `styles.css`, the viewer's class, which must come after `.viewer`, whose `position` it overrides. Every element's computed style, pseudo-elements and box on the start page, the runs dialog, the replay in nine states (interrupted, its fork question open, running and followed, queued at a pace off the list, failed, finished, a fork whose parent is kept, a fork held at its frontier, at its end), the builder, the viewer and the reference page, in both themes, at 1280 and 720 px wide, 8,688,324 values, was what it was; the header's padding moved by 1 px showed 5,140. The page stylesheets' guard holds the replay's rules too. **Its controls, a named visual change:** *Previous day*, *Play* or *Pause* and *Next day* are `IconButton`s, *Play* `primary`, their drawings `StepBackIcon`, `PlayIcon`, `PauseIcon` and `StepForwardIcon` of `src/icons/`; *Follow the newest day*, *Fork from here* and the fork question's answers are `Button`s, and *The run it came from* a `LinkButton`. `.replay-button` and `.replay-back` went, which wrote out `.ds-button`'s rule, and the transport draws as before: its buttons' padding is the component's 0, their boxes held at 44 and 52 px by their least sizes. The header's status is a `StatusChip` in the start page's tones, its sides 12 px (`--space-5`) where `.landing-status` drew 10; `.landing-status` left `landing/landing.css`, and its `OFF_SCALE` entry the guard. `StatusChip` takes a `label`: a chip so named is a live region, as the replay's is, *Run status*, which 13 tests now find by role and name rather than by a test id. The fork question's *Make the fork* is primary again: it wore `.landing-button-primary`, which went with P19.8's controls; a panel's fork question keeps the browser's buttons until P19.11. Moved: the replay's two page baselines, for the chip. The styles went from 34.95 to 34.13 kB, within their 36.1 kB budget, which did not change; the scripts weigh 1,719.83 kB. Not delivered: the pace's select stays the replay's own, with its 10 px sides in `OFF_SCALE`, as `Field` would add a label the line already has |
| P19.11 | The viewer's panels, a folder a pull request; `Fold` first. Baselines of a run's panels are added first, with a fixture of one scenario's answers, as `/view?scene=example` shows few. Moving a panel's controls to `compact` is a named visual change and not neutral, as in P19.9. | its stylesheets neutral; `compact` names what moves | Done, in ten pull requests, with P22.8 in three more. **A run's panels drawn first (#679):** `page-run-panels-dark` and `-light`, the info panel of a replay of the reference greenhouse at day 2, 12:00, every fold open and its fork question asked, in a view 3,000 px tall, at no tolerance; the simulator's answers about that run at that moment recorded by `scripts/recordRunAnswers.ts` into `e2e/visual/runAnswers.json.gz` (116 kB, the scene without its plants' organs), which the viewer checks against its contracts as it reads them. Each image is about 200 kB, over the 100 kB a page's was to stay under, for a panel with every fold open. **`Fold` first (#683), neutral:** the eight folds whose classes two rules listed, and the choice of what to show, are `Fold`, whose rules those two were; a summary's test id moved to a span in it. **Its stylesheets, neutral, a folder a pull request:** `fields/fields.css` (#684), then what was left of `styles.css` to `viewer.css` (#685), so that `styles.css` is its imports alone and each folder's sheet comes after the rules all panels share, as it stood: cut first, the weather's `.weather-panel dl` lost to `.info-panel dl`; then `weather/weather.css` (#686), `sensors/sensors.css` and `qaMode/qaMode.css` (#691), `timeline/timeline.css` and `checkpoints/checkpoints.css` (#694), `plants/plants.css` and `cfd/cfd.css` (#695). Each cut moved its folder's rules as written and in their order. Every element's computed style, pseudo-elements and box, on the start page in four states, the runs dialog in two, the replay in nine, a run's panels open and folded, a scenario's own view open, folded, with probes placed, with a sensor and with the camera selected in QA mode, the plant lab, a CFD case's boundaries, the builder, the viewer and the reference page, in both themes, at 1280 and 720 px wide, was what it was after each: in the end 108 states and 18,830,320 values; `.field-controls` 1 px lower showed 1,198. The probes' state came after review found #684's first commit moved the probes' cells (`.field-probes th` under `.info-panel th`), which it showed by 832 values; c253d97e made them `.field-probes table th` and `td`. A test holds each panel folder's sheet: a rule whose classes only that folder's sources write stands there, and a rule there names a class they write (`PANEL_STYLESHEETS`). **Its controls, a named visual change, in two:** every button of the info panel's cards (#696), and of the HUD, *Controls*, *What am I seeing?*, the field legend, the inspector, a camera's passes, a move's panel and the plant lab (#697), is `Button`, `compact`, 24 px at least each way, drawn from the tokens where the browser drew it at 21: P19.12's "`Button` drawn from tokens … on the panels" taken with it; *Controls* and *What am I seeing?*, which stand over the scene alone, keep a panel's ground and the panels' 13 px. A panel's fork question's *Make the fork* is `primary` again: it wore `landing-button-primary`, whose rule #674 took away, and had been drawn as the browser's plain button since; `useForkQuestion` takes its buttons' size. A camera's pass shown is in `--action`, the 600 weight that told it apart being every button's. The panels' other `<details>` are `Fold`, their line taking the pointer and 4 px under it once open; `Fold` keeps the browser's state when no page keeps it. Moved: the run panels' and the viewer's page baselines, both themes, and the reference QA's two camera views, whose passes are its buttons. The styles weigh 33.99 kB, from 34.19, within their 36.1 kB budget. Not delivered: selects, inputs, ranges and boxes to tick stay the browser's, as `Field` would add a label each panel row has; the HUD's header, which is dragged; links drawn as links; the labels over the scene and the QA pages' captions stay in `viewer.css`, not being panels; a plant's actions and history, drawn only for a plant chosen in the scene, were in no compared state |
| P19.12 | The named visual changes below, one pull request each, each taken or not on its own. | names what moves | Done, in five pull requests and #610 before them: every named change below is taken but *Off-scale values onto the scale*, which is not. Each of the 35 entries `OFF_SCALE` keeps says in `styles.test.ts` why its value stays, and the guard still refuses one that is new or gone. The final QA, below, walked what they changed. **A first visit follows `prefers-color-scheme`:** with no theme chosen in this browser, a page opens in the system's, dark if it says none, in the page's head (`index.html`) as in `storedTheme` (`design/theme.ts`); one chosen on the info panel's last line is kept and wins, as before. Nothing is kept until one is chosen, so that a later visit follows the system as it then is. The browser specs, the visual checks, the benchmarks and the demo ask for a dark system (`colorScheme`), so that no baseline moved; `e2e/panels.spec.ts` asks for a light one. Held by `design/theme.test.tsx`, `indexPage.test.ts` and `e2e/panels.spec.ts`. **A field's edge at 3:1, from what `CONTRAST_FAILURES` lists:** `--border` is a card's, a divider's, a dialog's and a chart frame's line, and a plain button's outline, which need no ratio, a button's words or icon identifying it; it was also the only edge of the replay's pace, a select, at 1.22 to 2.09. So `--border` stays theirs, and a field a page draws itself takes `--border-control`, #7a8699 dark and #767676 light, as strong as the browser draws its own fields' (#858585, #767676): 5.08 on the dark page and 3.63 on its panel at their worst backdrop, 4.18 and 3.45 on the light. It edges the replay's pace and the start page's and runs dialog's fields, `.landing-input`, which was `--text-muted`, so that one token is a field's edge. Held by `styles.test.ts`: the control pair reads `--border-control` for `--border`, whose four failures left `CONTRAST_FAILURES`, and a field's edge in `--border` fails. Moved: the start page's, the runs dialog's, the replay's and the reference page's baselines, both themes. The styles weigh 34.21 kB, from 34.15, within their 36.1 kB budget; the scripts 1,722.28 kB. Not delivered: the charts' pairs, `--chart-*` and `--data-*`, still listed, which change what the charts draw; the fields the browser draws, on the builder and the panels, whose edge is the browser's own; and a plain button's outline, which stays `--border`, as moving it would move the reference QA's two camera views, whose passes are buttons. **Buttons by what they do, from the [QA of 2026-11-04](qa-2026-11-04.md):** `--danger` is what cannot be taken back, red, #ff7b72 dark and #b42318 light, where `danger` was `--warn`'s orange; `--go` what sets a run going, green, #3fb950 dark and #1b6e33 light, `Button`'s and `IconButton`'s tone `go`. Each is a button's words or icon and its outline, as `primary`'s are, on no ground of its own, so that neither needs a colour for words on it: `--danger` is 7.43 on the dark page and 5.31 on its panel at their worst backdrop, 6.05 and 5.00 on the light; `--go` 7.37 and 5.27, 5.81 and 4.80. Every *Delete* is `danger`, a run's row's on the start page and in the runs dialog and the replay's, where they were plain, as the question's *Delete …* and *Stop and delete …* were already; the replay's *Play* is `go`, where it was `primary`, and so is *Pause*, the same button turned, so that it keeps its colour as it is pressed and its icon says which. The reference page shows both tones in each size and state. Held by `styles.test.ts`, whose pairs read both tokens for words and for an outline, `design/Button.test.tsx`, `landing/RunDelete.test.tsx`, `replay/ReplayTransport.test.tsx` and `e2e/design.spec.ts`, which names and measures the new tone's controls. Moved: the start page's, the runs dialog's, the replay's and the reference page's baselines, both themes. The styles weigh 34.33 kB, from 34.21, within their 36.1 kB budget; the scripts 1,722.31 kB. Not delivered: a filled button, and a colour for words on one, as no tone is filled; `--warn` stays a problem's, on a chip, a notice or a field. **`color-scheme` set once** was taken with #610: `design/base.css` sets it on `html` from `--scheme`, as the guard holds `:root` to custom properties, and no other rule sets it. **Alerts in `--warn`:** the 26 alerts drawn in the text's colour are drawn in `--warn`. 23 are `Notice`, `problem`, which now takes a test's id; the replay's refusal, in `--warn` already, and its *Opening the run…*, a status, are `Notice` with them. The scene's status on the chooser's line, a `span` where a paragraph cannot stand, and the plants that break the structure's rules, a list a paragraph cannot hold, take a class of their own, `.source-problem` and `.lab-rule-problems`. Two rules that set a colour over `Notice`'s give way to it: a QA page's caption that says its address cannot be drawn (`.qa-caption[role="alert"]`), and the replay's title (`.replay-title p:not([role="alert"])`), as the start page's cards do. A notice has no margin of its own, so an alert that was a paragraph with the browser's 1em above and below is spaced by its neighbours' margins. Every role and word the tests read stays. Moved: no baseline, as none shows an alert. Held by `styles.test.ts`, which refuses an alert, a problem `Notice`'s or an element's whose role is one, that no rule draws in `--warn`; by the panels' unit tests, which find each a problem `Notice`; and by `e2e/qa.spec.ts`, `e2e/replay.spec.ts` and `e2e/checkpoints.spec.ts`, which compare an alert's computed colour with `--warn`'s. The styles went from 34.33 to 34.46 kB, within their 36.1 kB budget; the scripts weigh 1,722.40 kB. **One focus ring on every control:** `design/base.css` draws focus, where the keyboard puts it, in one ring of the tokens, `--focus-width` of `--action` at `--focus-offset`, on every control and whatever a page focuses: fields' inputs and selects, ranges, boxes to tick, links, a fold's line and the panels' stripes, which the browser drew in its own ring, take the one the buttons wore. `.ds-button`'s and `.home-button`'s rules, which wrote it out, went. The replay's handle, whose own edge is 3 px of `--action`, keeps a ring of its fill, `--text`, by its colour alone; a panel's stripe keeps its hover's ground beside the ring, and reads at its 14 px. `FOCUS_RINGS` holds those three, and `styles.test.ts` refuses a rule beside the one that draws a ring's width, style or offset; the ring's `--action` is held at 3:1 on the page and on a panel by the contrast test, as a control's outline. Held by `e2e/design.spec.ts`, which tabs through the reference page and finds the ring on a button, a link, an input, a select and a fold's line, `e2e/panels.spec.ts` on a stripe and `e2e/replay.spec.ts` on the handle. Moved: no baseline, as the only controls the page baselines draw focused, the reference page's *focused* button and the runs dialog's *Close*, wore the ring already. The styles went from 34.46 to 34.29 kB, within their 36.1 kB budget; the scripts weigh 1,722.40 kB |

### Named visual changes

Separate from the above, each seen in review, none required by it:

| Change | Moves |
| --- | --- |
| Off-scale values onto the scale (`OFF_SCALE`, 40) | Page baselines; `renderer` and others with a legend or label |
| One focus ring on every control | Keyboard focus only; the reference page |
| `compact` at 24 px at least (WCAG 2.2's 2.5.8), from 13 to 21: what moving a control to it does, `--target-compact` being its floor since P19.6 | Panels and builder grow taller: 59 of 63 and 20 of 20 controls |
| The four button families' differences: padding 12 or 18, a page's ground or none | Landing, replay |
| `Button` drawn from tokens on the builder and panels, not by the browser | All panels: the largest change here |
| Alerts in `--warn`: the 17 bare ones | Panels, when each shows |
| Contrast: what `CONTRAST_FAILURES` lists. The builder's words on a ground no pair of tokens can show are held by `e2e/builder.spec.ts`: its note on a view with no ground of its own, 2.16 on the browser's white in the dark theme, is 8.66 on its dark ground since #610, and its placeholder took `--text-muted` in [P17's clean-up](p17-cleanup.md) | Charts, control outlines |
| A first visit follows `prefers-color-scheme`, not always dark | First visit only |
| `color-scheme` set once on `:root`, not in five rules | Scrollbars and controls outside those rules |
| Buttons by what they do, from the [QA of 2026-11-04](qa-2026-11-04.md): *Delete* in a red role and *Play* in a green one, each a token of its own (`danger` is `--warn`'s orange today, and no green role exists) | Every *Delete* and *Play*, once pages use `Button` |

## What must stay stable

The scene's drawing, the 27 QA baselines, a person's stored theme, the bundle
budget's check, and the viewer's behaviour and roles, which browser tests read.

## Out of scope

The scene's rendering and palette; any new visual design beyond the changes named
above; the charts' drawing; a component library published for others; a new page.

## Acceptance criteria

- `styles.test.ts` fails on a raw colour or size anywhere outside the tokens, its
  exceptions named, and `OFF_SCALE` holds only what is still there.
- P19.1's digest and the page baselines are unchanged from before P19.2 to after
  P19.5, and the page baselines through P19.11, but for moves to `compact`.
- A control on the reference page has a name and its target, in both themes.
- The contrast test computes every declared pair in both themes, and lists its
  failures by name.
- One mechanism sets the theme, and `panelTheme.ts` and `data-panels` are gone.
- Scripts and styles stay within budget, and any raise says why.

## Final QA scenario

On the built viewer, in both themes: walk the landing page, the runs dialog, the
builder and the replay, and open each panel of the reference greenhouse, by mouse
and by keyboard alone. Each looks as before P19.2, but for the visual changes taken;
focus is visible at each step; `/qa/design` shows each component in each state; and
the status of a failed run reads the same with colour removed.

### Recorded at `e23ccf6e`

Run on 11 November 2026 on `e23ccf6e`, on an Intel Core i9-14900K, 32 threads, 31 GB,
Linux, shared with other work. The API ran from the workspace's Python, with a state
folder and a port of its own. The viewer was its production build, served by `vite
preview` and pointed at that API. The browser was Playwright 1.65's headless Chromium 158,
driven by a script and drawing in software (SwiftShader), at 1280 by 720 and 720 by 720. Each theme was set as a person keeps
it (`greenhouse-sim.panels`), and the system's scheme was set the same. The reference
greenhouse was run once from the runs dialog's form, all 120 days. The failed run is part 8.

**How it was compared.** "Before P19.2" is `9f205955`, the commit P19.2 (#501) was merged
onto: P19.1's proofs, and none of the tokens. It was checked out beside `e23ccf6e`. Its
viewer was built and served the same way, against an API and a state folder of its own,
and its reference greenhouse was run the same way. Two comparisons were made. Each was a
pixel diff, and every difference it found was then looked at in the images:

- **CI's drawings.** The 10 page baselines P19.1 drew at `9f205955` (the start page, the
  runs dialog, the builder, the replay and the viewer, each in both themes), against those
  at `e23ccf6e`. Both sets were drawn by CI's container from the pages' answers.
- **This machine's.** At each commit: the start page, the reference greenhouse's runs
  dialog, the builder's first step, the replay of its run, that replay's panels, and the
  panels of `/view?scenario=reference_greenhouse`. Each was drawn in both themes and at
  both widths, 24 pairs, with every fold open; the panels were drawn in a view 3,000 px
  tall. What the stylesheet does not draw was left out, as the baselines leave it out
  (`e2e/visual/pages.css`).

Every pair differs, since other work changed these pages in the meantime: P18.5, P22.1
to P22.9, and fixes. Each visible difference is listed below, with the change it came
from. No difference was found that a change does not account for.

**By keyboard alone.** Each page was tabbed through from its top until focus came round
again, at each width and in each theme. At each stop the script read what had focus,
whether it matched `:focus-visible` and its computed outline, and took a clip of it. Every
clip was looked at. A closed fold that Tab reached was opened with Enter. The runs dialog
was opened from the start page's search, by typing the scenario's name and Enter, and
closed with Escape. The builder's house was drafted with Enter on *Draft this house*,
and the step that followed was walked. On the replay, PageUp moved the timeline's handle.

| Part | Result | What was seen |
| --- | --- | --- |
| 1. The start page | Passed, but for one stop of Tab, lost before P19 as now; fixed in #709 | By mouse: the search opened the reference greenhouse's runs dialog, and *Open the builder* opened the builder. By keyboard: 7 stops, each in the ring, 3 px of `--action` at 2 px. Tab from the search left focus on nothing for one press, with no ring drawn. The search's list of scenarios scrolls, so Chromium makes it a stop of Tab; the search then loses focus and closes the list, and focus falls to the page's body. It was so at `9f205955`. Fixed in #709, with a browser test. |
| 2. The runs dialog | Passed | By mouse: opened from a search's option, its run started from its form, closed by *Close*. By keyboard: Enter in the search opened it, with focus on *Close*, in the ring. 11 stops, each in the ring. The dialog itself is one of them, since it scrolls, and is ringed whole. Escape closed it, and focus went back to the search, in the ring. |
| 3. The builder | Passed, but for the date's calendar button | First step: 21 stops, each in the ring. After *Draft this house* (Enter, and by mouse a click): 65 stops. The run step's *Starting on* is a date field the browser draws, and takes four stops: its month, day and year, each in the ring, and then its calendar button. On that button the browser draws its own 1 px box round the icon, not the ring: focus can be seen, but faintly. |
| 4. The replay | Passed | By mouse: *Play* played the run, and *Pause* stopped it. By keyboard: 79 stops at 1280 px and 76 at 720, each in the ring. They are the header's controls, the panels' (each fold opened by Enter), the HUD's and the transport's. The handle wears a ring in `--text`, its named exception. PageUp moved it from Day 1, 00:00 to Day 1, 24:00. Two radio buttons of the air field's view were not Tab stops; they are reached by the arrow keys, as radio buttons in a group are. |
| 5. Each panel of the reference greenhouse | Passed | By mouse, every closed fold of the info panel was clicked until none was left: 7 on `/view?scenario=reference_greenhouse`, and 11 of the replay's 12 (the twelfth opens open), in each theme. A click leaves no ring: *Top*, clicked, is focused, does not match `:focus-visible`, and has no outline. By keyboard, the same folds were opened by Enter: 58 stops on the view at 1280 px and 56 at 720, each in the ring, the panels' stripes among them. |
| 6. Focus at each step | Passed, but for parts 1 and 3 | Of 1,086 stops on every page, in each theme and at each width, 1,082 wore the one ring. The other 4 are the builder's calendar button (part 3). The start page's lost press (part 1) is not a stop: nothing has focus. |
| 7. `/qa/design` | Passed | Every component of `src/design/` is on it. `Button`, `LinkButton` and `IconButton` are shown in each tone (plain, primary, danger, go) at each size (target, compact): enabled, disabled and, but for the icon, as a link, which cannot be disabled; one is drawn focused. `Field` is shown as a plain field, with a hint, with a problem, disabled, as a choice, and compact as a field and as a choice. `StatusChip` is shown in each tone (plain, active, problem) and with a note; `Notice` as a status and as a problem; `Fold` open and folded. Every token is shown too. No component has a hover or pressed rule (`components.css` holds `:disabled` and `[open]` alone), so there is no such state to show. The ring on a link, a field, a choice and a fold's line is not drawn on the page; the keyboard walk found it on each of its 33 stops, as `e2e/design.spec.ts` does. |
| 8. A failed run's status, colour removed | Passed | `climate_box` was run under `{"worker_memory_bytes": 180000000}`, given with `--limits`. It failed at day 1 of 14: "its worker held 182.1 MB of memory, past the limit of 180.0 MB on one worker". Its chip says *Failed* in words, on the start page, in the runs dialog and in the replay's header, where it is the live region *Run status*. The row and the header say the reason beside it. Seen through `filter: grayscale(1)` on the page, and through Chromium's emulated achromatopsia, in each theme, it reads the same: it has no icon, and its word is what says it. The filter does not reach the runs dialog, which the browser draws in its top layer, so there only the emulation removed the colour. |

**What looks different from before P19.2,** page by page. A change marked *named* is one
of P19's named visual changes, as its step's row says; the others are other steps' or
fixes'.

- **Every page, in the dark theme:** the ground behind the builder's view and behind the
  viewer's panels is dark, where it was the browser's white. So the panels, which are
  translucent, look darker, and a panel card's title no longer sits on a darker patch.
  *Named*: `color-scheme` set once (#610).
- **The start page:** its title, its two cards one above the other with *or* between,
  each with an icon, and the search's words (P22.7, #675). The room's line, and each
  run's usage under its row (P18.5, #626). *Delete* on a row (#567). *Named*: buttons'
  sides 12 px where they were 18, with no ground of their own, and a chip's sides 12 px
  where they were 10 (P19.8, #674); *Delete* in red (#707); the search's edge in
  `--border-control` (#704).
- **The runs dialog:** a new run's form first, with its days, weather, pace and seed and
  *Make a new scenario from this one*, and *Open in the viewer* and *New run* gone from
  its head (P22.4, #646 and #653). Its rows are as the start page's. *Named*: *Close*,
  focused as it opens, in the ring (P19.8); *Delete* in red; the fields' edges.
- **The builder:** *named*, its inputs, selects and buttons are drawn from the tokens at
  24 px, where the browser drew them at 21, and its labels are 13 px at 600 in
  `--text-soft`, where they were 14 px in `--text` (P19.9, #638 and #639). At 720 px wide
  its form stands above the view, where the two stood side by side (#544).
- **The replay:** its title *Run of …* (P22.8, #699); "the scenario's seed" for a run
  started with none (P22.4); "120 of 120 days computed" (#616); "Shows a day in" and
  "10 s" (P22.5, #664); *Delete* where *Other runs* stood, and a stripe that folds the
  controls under the view (P22.9, #678); the timeline's end always labelled, and "not
  computed yet" said only while some is (#504). *Named*: *Play* and *Pause* in green,
  where *Play* was blue, and *Delete* in red (#707); the chip's sides 12 px where they
  were 10 (P19.10, #677); the pace's edge in `--border-control` (#704). The transport's
  buttons, now `IconButton`s, are drawn as before.
- **The panels:** the heading names the run or the simulation (P22.8, #699); *Follow*
  is gone (P22.3, #655); *Vanthoor house* is listed (#648); the timeline has a plan's
  lane (P22.3); a Display card, and the equipment in groups (P22.8, #700 and #701); the
  stripe that folds the info panel runs its height (P22.9, #678); a panel's lines are 1.2
  of its text's size where they were the font's own, so its weather's list is tighter
  (#613); what lies behind a panel is blurred (#549). *Named*: every button of the
  panels and the HUD is drawn from the tokens, `compact`, at 24 px at least, where the
  browser drew it at 21 (P19.11, #696 and #697); an open fold's line has 4 px under it
  (P19.11).

**The acceptance criteria.**

- **`styles.test.ts` refuses a raw colour or size outside the tokens:** its tests, 83
  with the design components' and `indexPage.test.ts`, pass on this commit. They refuse a
  raw colour or size wherever and however it is written. The exceptions are named, and
  `OFF_SCALE`'s 35 entries are compared both ways with what the stylesheet holds, so
  that an entry gone fails as an entry missing does.
- **The digest and the page baselines did not change from before P19.2 to after P19.5,
  nor the baselines through P19.11, but for moves to `compact`:** from git. No P19.2 to
  P19.5 pull request (#501, #502, #517, #547, #551) changed `RESOLVED_DIGESTS` or a page
  baseline. The digest moved five times in that span, each in another change to the
  stylesheet, in its own diff, as the design allows: #495, #521, #536, #544 and #550.
  Through P19.11, P19's pull requests moved the reference page's baselines (#577 and
  #630, its components, and #639, `Field`'s size), the builder's (#638 and #639, `compact`), the start page's and
  the runs dialog's (#674, its buttons and chips), the replay's (#677, its chip), and the
  viewer's and a run's panels (#696 and #697, `compact`). #674's and #677's moves were for
  named changes other than `compact`, as their rows say.
- **A control on the reference page has a name and its target, in both themes:**
  `e2e/design.spec.ts`, which passes on this commit, 36 tests with `e2e/panels.spec.ts`.
- **The contrast test computes every declared pair in both themes, and lists its
  failures by name:** `styles.test.ts`. `CONTRAST_FAILURES` lists 14, all of them the
  charts' words and lines and a compass's ring.
- **One mechanism sets the theme:** `design/theme.ts` writes `data-theme`.
  `panelTheme.ts` is gone, and nothing in `src/` or `index.html` writes or reads
  `data-panels`.
- **Scripts and styles stay within budget:** the build's check passed. The styles weigh
  34.29 kB against 36.1, and the scripts 1,722.40 kB against 1,765; at `9f205955`
  they weighed 28.48 and 1,750.20 kB. Each raise says why, in the step that made it:
  P19.4, P19.5, P19.6, P19.7 and P19.9.

**Not walked.** A plant's actions and history, shown only for a plant chosen in the
scene. The builder's later items and inspector, walked only to its run step; P19.9's
browser test walks its house form and palette by keyboard. The QA pages other than
`/qa/design`, whose 27 baselines CI compares. Another browser than Chromium, and a
screen reader. The scene, which the themes do not change by design.

**Found.** One defect, in part 1: the start page's search lost a press of Tab. It is
older than P19, and is fixed in #709 with a browser test that fails without the change.
One gap, in part 3: a date field's calendar button is focused in the browser's thin box,
not the one ring, since `:focus-visible` matches neither the field nor its button inside
it. It is left as found: a rule for a browser's inner part is a decision of its own, and
the guard admits no other `:focus-visible` rule.

## Settled in review

1. **The compact size.** 44 px on pages; in panels and forms, `compact`, with 24 px
   as its minimum, taken as a named visual step.
2. **The panels' browser-drawn look** stays through the neutral steps. Drawing their
   buttons from tokens is a visual step of its own.
3. **The named visual changes** are taken one by one.
4. **The styles' budget** goes to about 32 kB in the step that needs it, P19.4, and
   to 34 kB in P19.5, when spacing and the columns of a list of runs together cross it.

## Open questions

Carried to [future work](../future-work.md#the-design-system-after-p19) as P19 closed.

1. **Whether the no-tolerance images stay stable** as more of them are drawn. They
   did over two runs of one commit. If the pinned container is not stable to the
   pixel for a page's text, the fallback is a comparison of computed styles per
   element: exact and with no images, but blind to layout.
2. **A change of `font-weight` alone.** The pinned container draws 600 no
   differently from normal in these images, so they may not see it. A component's is
   held by a test of its computed weight on the reference page (P19.6). A page's own
   rule is held by the digest, and by nothing once it goes (P19.8).
