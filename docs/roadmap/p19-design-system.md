# P19: The viewer's design system

**Status:** in progress (P19.1 to P19.7 are done): the design below, with decision
[0068](../decisions/0068-the-viewers-design-system-is-its-own-tokens-and-components.md).
Part of the [simulator roadmap](README.md).

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
| P19.8 | The digest goes, its rules starting to move. The landing page: its stylesheet moved in two parts, then its controls moved to components. **After the changes in progress to `RunsDialog.tsx` and the new-run form have merged,** since they touch the same lines. | neutral | Proposed |
| P19.9 | The builder: its stylesheet, then its controls. Moving them to `compact` is a named visual change and not neutral: they go from the browser's drawing at 21 px to the tokens' at 24. Selectors `e2e/builder.spec.ts` reads change with it, to roles where they can. With it, from [P12's QA](archive/p12-setup-builder.md#the-first-days-check): the house form's labels *Origin Position X* and *Origin X* say what tells them apart, and the house form and palette are walked by keyboard alone; and from the [QA of 2026-11-04](qa-2026-11-04.md#where-each-went), the run step's form laid out at 720 px high. | its stylesheet neutral; `compact` names what moves | In progress: its stylesheet moved, neutral. `builder/builder.css` holds the builder's rules, imported after the components' and so before the viewer's: the order changed, so the digests moved, and nothing the builder draws did. Every element's computed style on the builder, in both themes, at 1280 and 720 px wide, in seven of its states, is what it was, and its two baselines did not move. A test keeps a page's rules in its own stylesheet. The styles weigh 35.93 kB, as before |
| P19.10 | The replay: its stylesheet, its transport to `IconButton`, its four icons to `src/icons/`. | neutral | Proposed |
| P19.11 | The viewer's panels, a folder a pull request; `Fold` first. Baselines of a run's panels are added first, with a fixture of one scenario's answers, as `/view?scene=example` shows few. Moving a panel's controls to `compact` is a named visual change and not neutral, as in P19.9. | its stylesheets neutral; `compact` names what moves | Proposed |
| P19.12 | The named visual changes below, one pull request each, each taken or not on its own. | names what moves | Proposed |

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
| Contrast: what `CONTRAST_FAILURES` lists. The builder's words on a ground no pair of tokens can show are held by `e2e/builder.spec.ts`: its note on a view with no ground of its own, 2.16 on the browser's white in the dark theme, is 8.66 on its dark ground since #610, and its placeholder took `--text-muted` in [P17's clean-up](archive/p17-cleanup.md) | Charts, control outlines |
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

## Settled in review

1. **The compact size.** 44 px on pages; in panels and forms, `compact`, with 24 px
   as its minimum, taken as a named visual step.
2. **The panels' browser-drawn look** stays through the neutral steps. Drawing their
   buttons from tokens is a visual step of its own.
3. **The named visual changes** are taken one by one.
4. **The styles' budget** goes to about 32 kB in the step that needs it, P19.4, and
   to 34 kB in P19.5, when spacing and the columns of a list of runs together cross it.

## Open questions

1. **Whether the no-tolerance images stay stable** as more of them are drawn. They
   did over two runs of one commit. If the pinned container is not stable to the
   pixel for a page's text, the fallback is a comparison of computed styles per
   element: exact and with no images, but blind to layout.
2. **A change of `font-weight` alone.** The pinned container draws 600 no
   differently from normal in these images, so they may not see it. A component's is
   held by a test of its computed weight on the reference page (P19.6). A page's own
   rule is held by the digest, and by nothing once it goes (P19.8).
