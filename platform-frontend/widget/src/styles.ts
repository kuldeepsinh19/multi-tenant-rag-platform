import { TOKENS_CSS } from "./generated/tokens";

/**
 * The widget cannot import the dashboard's CSS (separate bundle, and it must not
 * leak styles into or inherit them from a customer's page), so the design tokens
 * are inlined here. The interpolated block below is GENERATED from
 * src/styles/tokens.css by widget/scripts — it is not hand-maintained, and a
 * drift test fails the build if the generated output stops matching the source.
 * An earlier hand-copied version claimed to be identical to tokens.css and had
 * quietly drifted; generating it is what makes that claim true.
 *
 * Everything is scoped under .pcw-root and defensively reset, because the host
 * page's stylesheet is unknown and may target bare elements. Custom properties
 * are declared on .pcw-root rather than :root for the same reason — writing to
 * :root could collide with the host page's own variables.
 *
 * The type-scale tokens (--pcw-fs-*) are px-valued on purpose: rem would resolve
 * against the HOST page's root font-size, so a customer with `html { font-size:
 * 10px }` would shrink the whole widget.
 */
export const STYLE = `${TOKENS_CSS}
/* --pcw-shadow is deliberately NOT generated. tokens.css has no matching
   elevation — it is neither --e-3 nor --e-4 — because the widget's floating
   panel sits over an unknown host page and needs heavier elevation than any
   in-app surface, which always sits on our own known background. It is
   therefore excluded from the generator's allowlist and kept by hand here. */
.pcw-root {
  --pcw-shadow: 0 18px 44px -16px rgba(13, 20, 19, 0.35);
}

/* The widget follows the visitor's OS preference — there is no in-widget toggle,
   since it lives on someone else's page. */
@media (prefers-color-scheme: dark) {
  .pcw-root {
    --pcw-shadow: 0 18px 44px -16px rgba(0, 0, 0, 0.7);
  }
}

.pcw-root *,
.pcw-root *::before,
.pcw-root *::after { box-sizing: border-box; }

.pcw-bubble {
  position: fixed; bottom: 16px; right: 16px;
  display: flex; align-items: center; justify-content: center;
  width: 56px; height: 56px; padding: 0;
  /* A literal 50%, not --pcw-r-full: this is a CIRCLE. The pill token renders
     identically on a square box but would silently become a stadium if the box
     ever stopped being square. */
  border-radius: 50%; border: none; cursor: pointer;
  color: var(--pcw-accent-ink); background: var(--pcw-accent);
  box-shadow: var(--pcw-shadow);
  z-index: 2147483000;
  transition: transform var(--pcw-dur) var(--pcw-ease-out), background-color var(--pcw-dur) ease;
  /* 320ms entrance kept literal — no duration token matches, and snapping it to
     --pcw-dur would change the motion signature. */
  animation: pcw-bubble-in 320ms var(--pcw-ease-spring) both;
}
.pcw-bubble:hover { background: var(--pcw-accent-hover); transform: scale(1.06); }
.pcw-bubble:active { transform: scale(0.96); }
.pcw-bubble:focus-visible { outline: 2px solid var(--pcw-accent); outline-offset: 2px; }

.pcw-panel {
  position: fixed; bottom: 84px; right: 16px;
  /* Was a fixed 320px + 20px offset, which overflowed a 320px viewport. */
  width: min(360px, calc(100vw - 32px));
  max-height: min(70vh, 560px);
  display: flex; flex-direction: column;
  color: var(--pcw-text); background: var(--pcw-surface);
  border: 1px solid var(--pcw-border);
  border-radius: var(--pcw-r-lg);
  box-shadow: var(--pcw-shadow);
  overflow: hidden;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  /* px, not rem — see the note above: rem would resolve against the host page. */
  font-size: var(--pcw-fs-base); line-height: 1.5;
  z-index: 2147483000;
  transform-origin: bottom right;
  /* 200ms kept literal: no token matches this entrance duration. */
  animation: pcw-panel-in 200ms var(--pcw-ease-out) both;
}
/* Any author-origin display value beats the UA sheet's [hidden] rule, so every
   element this widget toggles via the hidden property needs the guard restated.
   Declared once for the whole subtree rather than per element: .pcw-panel and
   .pcw-generating both set display, and the next one added would silently
   ignore hidden too. */
.pcw-root [hidden] { display: none !important; }

.pcw-header {
  display: flex; justify-content: space-between; align-items: center; gap: 8px;
  padding: 10px 12px;
  color: var(--pcw-accent-ink); background: var(--pcw-accent);
}
.pcw-header-title { font-weight: 600; letter-spacing: -0.01em; }
.pcw-header button {
  display: flex; align-items: center; justify-content: center;
  /* The 28x28 VISUAL box is kept deliberately: a real 44x44 control would push
     the accent header from 48px to 64px on a panel capped at 560px. The hit area
     is expanded to --pcw-tap by the ::after below instead. */
  position: relative;
  width: 28px; height: 28px; padding: 0;
  background: none; border: none; border-radius: var(--pcw-r-xs);
  color: inherit; cursor: pointer;
  transition: background-color var(--pcw-dur) ease;
}
/* WCAG 2.5.5 target size, hit area only. The pseudo-element is absolutely
   positioned so it contributes nothing to layout, which keeps the hover fill and
   the focus ring drawn on the 28px box. */
.pcw-header button::after {
  content: "";
  position: absolute;
  top: 50%; left: 50%;
  width: var(--pcw-tap); height: var(--pcw-tap);
  transform: translate(-50%, -50%);
}
.pcw-header button:hover { background: rgba(255, 255, 255, 0.18); }
/* Geometry is unified at 2px offset, but the COLOUR must stay --pcw-accent-ink:
   this button sits on the accent fill, where an --pcw-accent ring is invisible. */
.pcw-header button:focus-visible { outline: 2px solid var(--pcw-accent-ink); outline-offset: 2px; }

.pcw-messages {
  flex: 1; min-height: 0;
  display: flex; flex-direction: column; gap: 10px;
  overflow-y: auto; overscroll-behavior: contain;
  padding: 12px;
}
.pcw-empty { color: var(--pcw-muted); text-align: center; padding: 20px 8px; margin: 0; }

.pcw-message {
  max-width: 85%;
  padding: 8px 11px;
  border-radius: var(--pcw-r-lg);
  overflow-wrap: anywhere;
  animation: pcw-message-in var(--pcw-dur) var(--pcw-ease-out) both;
}
.pcw-message__role {
  display: block; margin-bottom: 2px;
  font-size: var(--pcw-fs-xs); font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  opacity: 0.75;
}
.pcw-message--user {
  align-self: flex-end;
  color: var(--pcw-accent-ink); background: var(--pcw-accent);
  /* Bespoke off-scale tail radius, chosen relative to the 14px corner. */
  border-bottom-right-radius: 5px;
}
.pcw-message--assistant {
  align-self: flex-start;
  background: var(--pcw-surface-2);
  border: 1px solid var(--pcw-border);
  /* Bespoke off-scale tail radius, chosen relative to the 14px corner. */
  border-bottom-left-radius: 5px;
}

.pcw-citations {
  list-style: none; display: flex; flex-wrap: wrap; gap: 4px;
  margin: 8px 0 0; padding: 0;
}
.pcw-citations-label {
  margin: 8px 0 4px;
  font-size: var(--pcw-fs-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--pcw-muted);
}
.pcw-citations li {
  padding: 2px 8px; font-size: var(--pcw-fs-xs);
  color: var(--pcw-muted); background: var(--pcw-surface-3);
  border: 1px solid var(--pcw-border); border-radius: var(--pcw-r-full);
}
.pcw-message--user .pcw-citations-label { color: inherit; opacity: 0.85; }
.pcw-message--user .pcw-citations li {
  color: inherit;
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(255, 255, 255, 0.28);
}

.pcw-escalated {
  display: flex; align-items: center; gap: 6px;
  margin: 8px 0 0; padding: 6px 8px;
  font-size: var(--pcw-fs-xs);
  color: var(--pcw-warning); background: var(--pcw-warning-bg);
  border: 1px solid var(--pcw-warning-border); border-radius: var(--pcw-r-xs);
}

/* Tone variants: a 429 rate-limit is not an error and no longer renders red. */
.pcw-banner {
  margin: 0 12px 8px; padding: 8px 10px;
  font-size: var(--pcw-fs-sm); border: 1px solid; border-radius: var(--pcw-r-sm);
  animation: pcw-banner-in var(--pcw-dur) var(--pcw-ease-out) both;
}
.pcw-banner--error {
  color: var(--pcw-danger); background: var(--pcw-danger-bg); border-color: var(--pcw-danger-border);
}
.pcw-banner--warning {
  color: var(--pcw-warning); background: var(--pcw-warning-bg); border-color: var(--pcw-warning-border);
}
.pcw-banner--neutral {
  color: var(--pcw-muted); background: var(--pcw-surface-2); border-color: var(--pcw-border);
}

.pcw-generating { display: flex; align-items: center; gap: 4px; padding: 0 12px 10px; }
.pcw-dot {
  /* 50% because this is a CIRCLE, not a pill — see .pcw-bubble. */
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--pcw-accent);
  /* 1.2s and the stagger delays below are a bespoke motion signature; no tokens
     exist at these values and snapping them would change the rhythm. */
  animation: pcw-dot 1.2s ease-in-out infinite;
}
.pcw-dot:nth-child(2) { animation-delay: 160ms; }
.pcw-dot:nth-child(3) { animation-delay: 320ms; }

.pcw-composer {
  display: flex; gap: 6px; align-items: flex-end;
  padding: 8px; border-top: 1px solid var(--pcw-border);
  background: var(--pcw-surface);
}
.pcw-composer textarea {
  flex: 1; min-width: 0; resize: none;
  /* WCAG 2.5.5: honest --pcw-tap height. Vertical padding raised from 7px so a
     single 21px row (14px x 1.5) stays optically centred in the taller box
     rather than hugging the top. */
  min-height: var(--pcw-tap);
  padding: 10px 9px;
  font: inherit; color: var(--pcw-text);
  background: var(--pcw-surface-2);
  /* Was #ccc at 1.61:1 — below the 3:1 WCAG 1.4.11 minimum for a control
     boundary. This value measures 4.12:1 on white. */
  border: 1px solid var(--pcw-border-control);
  border-radius: var(--pcw-r-sm);
  transition: border-color var(--pcw-dur) ease, box-shadow var(--pcw-dur) ease;
}
.pcw-composer textarea::placeholder { color: var(--pcw-muted); }
/* Intentionally NOT the 2px-outline ring used elsewhere in this file: this
   border-colour + box-shadow treatment deliberately mirrors the dashboard's
   .input:focus-visible pattern, so text inputs feel identical across both
   surfaces. A future "unify all focus rings" pass should leave this alone. */
.pcw-composer textarea:focus-visible {
  outline: none;
  border-color: var(--pcw-accent);
  box-shadow: 0 0 0 3px var(--pcw-ring);
}
.pcw-composer button {
  flex: none;
  /* WCAG 2.5.5: an honest resize from 34px — the composer can afford the height. */
  min-height: var(--pcw-tap); padding: 0 12px;
  font: inherit; font-weight: 600;
  border: 1px solid transparent; border-radius: var(--pcw-r-sm);
  cursor: pointer;
  color: var(--pcw-accent-ink); background: var(--pcw-accent);
  transition: background-color var(--pcw-dur) ease, transform var(--pcw-dur-fast) ease;
}
.pcw-composer button:hover:not(:disabled) { background: var(--pcw-accent-hover); }
.pcw-composer button:active:not(:disabled) { transform: scale(0.97); }
.pcw-composer button:disabled { opacity: 0.5; cursor: not-allowed; }
.pcw-composer button:focus-visible { outline: 2px solid var(--pcw-accent); outline-offset: 2px; }
.pcw-stop {
  color: var(--pcw-danger) !important;
  background: transparent !important;
  border-color: var(--pcw-danger-border) !important;
}

/* Clip-based visually-hidden. Replaces a left:-9999px label, which forces
   assistive tech to handle an off-canvas box and breaks under RTL. */
.pcw-sr-only {
  position: absolute !important;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0); clip-path: inset(50%);
  white-space: nowrap; border: 0;
}

@keyframes pcw-bubble-in {
  from { opacity: 0; transform: scale(0.6); }
  to { opacity: 1; transform: scale(1); }
}
@keyframes pcw-panel-in {
  from { opacity: 0; transform: scale(0.94) translate3d(0, 8px, 0); }
  to { opacity: 1; transform: scale(1) translate3d(0, 0, 0); }
}
@keyframes pcw-message-in {
  from { opacity: 0; transform: translate3d(0, 6px, 0); }
  to { opacity: 1; transform: translate3d(0, 0, 0); }
}
@keyframes pcw-banner-in {
  from { opacity: 0; transform: translate3d(0, -6px, 0); }
  to { opacity: 1; transform: translate3d(0, 0, 0); }
}
@keyframes pcw-dot {
  0%, 80%, 100% { transform: translate3d(0, 0, 0); opacity: 0.45; }
  40% { transform: translate3d(0, -4px, 0); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .pcw-root *,
  .pcw-root *::before,
  .pcw-root *::after {
    /* 0.01ms is the standard near-zero escape hatch, not a duration on the
       scale — tokenising it would defeat the point. */
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  .pcw-dot { opacity: 1; }
}
`;
