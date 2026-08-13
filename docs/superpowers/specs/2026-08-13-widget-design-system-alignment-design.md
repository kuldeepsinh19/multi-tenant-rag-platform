# Widget design-system alignment

**Date:** 2026-08-13
**Status:** Approved for planning
**Scope:** `platform-frontend/widget/`

## Problem

The dashboard is already one consistent system. `src/styles/tokens.css` is the single
source of truth for colour, space, type, elevation, and motion, and it is annotated with
measured WCAG ratios. No file under `src/**/*.css` hardcodes a colour.

The embeddable widget is the exception. `widget/src/widget.ts` carries a ~230-line CSS
string that re-implements that design system from memory:

| Concern | Widget today | App |
| --- | --- | --- |
| Palette | 16 `--pcw-*` hex literals per theme, hand-copied | `tokens.css`, annotated |
| Type | `10px`/`11px`/`12px`/`13px`/`14px` literals | `--fs-xs`…`--fs-3xl` in `rem` |
| Radii | `6px`/`8px`/`14px`/`999px` literals | `--r-xs`…`--r-full` |
| Motion | `120ms`/`180ms`/`320ms` + inline cubic-beziers, repeated 9× | `--dur*`, `--ease*` |
| Focus ring geometry | three different outline offsets | one global `:focus-visible` |
| Touch targets | header button 28px, send button 34px | `--tap: 44px`, enforced |

Two consequences beyond untidiness:

1. **Nothing prevents palette drift.** The `--pcw-*` values were correct when copied. A
   future change to `tokens.css` will not reach them, and the failure is silent — the
   widget keeps rendering, just off-brand or below contrast minimums.
2. **`px` type ignores user font-size preferences.** `tokens.css:24-25` deliberately keeps
   the root at 16px so `rem` honours the visitor's browser setting. The widget's `px`
   sizes opt every embedded visitor out of that.

## Non-goals

- **No visual redesign.** Where a widget value already equals its token (`14px` =
  `--r-lg`), substitution is byte-identical output.
- **No shared CSS modules.** The widget cannot import the app's CSS; it ships as one
  self-contained bundle onto third-party pages. Only *token values* are shared.
- **`prefers-color-scheme` stays.** The widget has no theme toggle and no access to the
  app's store, so following the host page's scheme is correct. The app's `data-theme`
  mechanism is not imposed on it.
- **`system-ui` font stack stays.** The widget must not pull a webfont onto a customer's
  page. Only the type *scale* is shared, not the family.
- **The `--pcw-*` prefix stays**, so widget variables cannot collide with host-page CSS.

## Design

### 1. Build-time token generation

A generator, `widget/scripts/gen-tokens.ts`, parses `src/styles/tokens.css` and emits
`widget/src/generated/tokens.ts` — a TypeScript module exporting the CSS custom-property
block as a string constant. `widget.ts` interpolates that constant at the top of its
existing style string.

The generator:

- Reads an explicit allowlist of token names — only what the widget uses, so the bundle
  does not grow by the full app palette.
- Renames each to the `--pcw-` prefix (`--accent` → `--pcw-accent`).
- Emits the `:root` block as the widget's light default.
- Emits the `:root[data-theme="dark"]` block wrapped in
  `@media (prefers-color-scheme: dark)`, preserving the deliberate mechanism difference
  rather than erasing it.
- Fails loudly if an allowlisted token is missing from `tokens.css`, rather than emitting
  an empty value that would render as `initial`.

The generated file is **committed**, so `npm run build` needs no extra step and the widget
build has no new runtime dependency.

### 2. Drift protection

`npm run gen:tokens` regenerates the file. A test asserts that regenerating produces
output identical to the committed file, so a `tokens.css` change without regeneration
fails CI instead of shipping a stale palette. This is the mechanism that makes the single
source of truth real rather than aspirational.

### 3. Scale substitution in the widget CSS

Beyond colour, the generated block also carries the radius, type, and motion scales the
widget uses. The hand-written literals in `widget.ts` are replaced with those variables.

Identity substitutions (no visual change): radii `6px`→`--pcw-r-xs`, `8px`→`--pcw-r-sm`,
`14px`→`--pcw-r-lg`, `999px`→`--pcw-r-full`; durations `120ms`→`--pcw-dur-fast`,
`180ms`→`--pcw-dur`; the two repeated cubic-beziers →`--pcw-ease-out` / `--pcw-ease-spring`.

### 4. Deliberate visual changes

These are the only changes that alter rendered output. Each is a correction toward a
standard the app already meets.

| Change | From | To | Reason |
| --- | --- | --- | --- |
| Message role label, citations label | `10px` | `--pcw-fs-xs` (12px, rem) | No 10px step exists; below comfortable minimum |
| Citation chips | `11px` | `--pcw-fs-xs` (12px, rem) | Same |
| Escalation notice | `12px` | `--pcw-fs-xs` (12px, rem) | Identity, now in `rem` |
| Banner | `13px` | `--pcw-fs-sm` (13px, rem) | Identity, now in `rem` |
| Panel body | `14px` | `--pcw-fs-base` (14px, rem) | Identity, now in `rem` |
| Header close button | 28×28 | 44×44 | WCAG 2.5.5; app enforces `--tap` |
| Composer send button | 34px tall | 44px tall | Same |
| Focus ring geometry | offsets `3px` / `1px` / `2px` | uniform `2px` solid, `2px` offset | Matches `base.css:` global `:focus-visible` |

Only ring *geometry* is unified. Ring *colour* stays context-dependent: the header button
sits on the accent fill, so it keeps `--pcw-accent-ink` — an accent ring would be
invisible there. The composer textarea likewise keeps its border-plus-`box-shadow` ring,
which mirrors the app's own `.input:focus-visible` treatment rather than contradicting it.

The touch-target changes are the largest visual delta: they make the header and composer
taller. The panel is `max-height: min(70vh, 560px)` with a flexed message list, so the
message area absorbs the difference and the panel does not grow.

### 5. File structure

`widget.ts` is 602 lines mixing CSS, markup, state, and SSE wiring. The generated tokens
already move ~45 lines out. Extract the remaining style string into
`widget/src/styles.ts` as a single exported constant, leaving `widget.ts` to behaviour.
No logic changes — a pure move, so any behavioural diff is a bug.

## Verification

- `npm run test` — existing widget tests pass unchanged; the token-drift test is new.
- `npm run typecheck`, `npm run lint`, `npm run build` all clean.
- The generated CSS block is diffed against the current hand-written block to confirm
  every colour value is byte-identical, isolating the intended visual changes in §4 from
  accidental ones.
- Manual check of the widget in both colour schemes at a 320px viewport, plus keyboard
  traversal confirming every focus ring is visible against its own background.

## Risks

- **Generator brittleness.** It parses CSS with a regex over a file it does not own. Held
  in check by the allowlist and the fail-loudly-on-missing-token rule: a `tokens.css`
  restructure breaks the build rather than silently emitting nothing.
- **Bundle size.** The allowlist keeps growth to the tokens actually used; measured before
  and after.
