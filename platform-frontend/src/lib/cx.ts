/** Joins class names, dropping falsy entries so variants can be applied
 *  conditionally: cx(ui.btn, ui.btnGhost, isActive && styles.active).
 *  Deliberately hand-rolled — this is the whole of `clsx` that we need, and the
 *  project adds no dependencies. */
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
