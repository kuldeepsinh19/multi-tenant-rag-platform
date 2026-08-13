import { cx } from "@/lib/cx";

import styles from "./Skeleton.module.css";

interface Props {
  /** How many placeholder blocks to draw. */
  count?: number;
  /** Row = list item height; tile = stat-card height. */
  variant?: "row" | "tile";
  /**
   * What a screen reader hears while loading. The visual blocks are
   * aria-hidden, so this label is the only accessible announcement — it replaces
   * the plain `<p>Loading …</p>` it stands in for and must not be dropped.
   */
  label: string;
  className?: string;
}

/** Shimmering placeholder for pending list/tile data. The shimmer is a
 *  background-position animation, so it is neutralized by the global
 *  reduced-motion rule and degrades to a flat block. */
export function Skeleton({ count = 3, variant = "row", label, className }: Props) {
  return (
    <div
      className={cx(variant === "tile" ? styles.tiles : styles.rows, className)}
      role="status"
      aria-busy="true"
    >
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          className={cx(styles.block, variant === "tile" ? styles.tile : styles.row)}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}
