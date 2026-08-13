import type { Business } from "@/api/businesses";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusMessage } from "@/components/ui/StatusMessage";
import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./BusinessList.module.css";

interface Props {
  businesses: Business[] | undefined;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | undefined;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function BusinessList({
  businesses,
  isLoading,
  isError,
  errorMessage,
  selectedId,
  onSelect,
}: Props) {
  if (isLoading) return <Skeleton count={3} label="Loading businesses…" />;
  if (isError)
    return (
      <StatusMessage tone="error">Couldn&apos;t load businesses: {errorMessage}</StatusMessage>
    );
  if (!businesses || businesses.length === 0)
    return <EmptyState title="No businesses yet." hint="Create your first one below." />;

  return (
    <ul className={styles.list}>
      {businesses.map((business) => (
        <li key={business.id} className={styles.item}>
          {/* aria-pressed is the single source of truth for selection; the CSS
              paints it via [aria-pressed="true"] rather than a parallel class. */}
          <button
            type="button"
            className={styles.trigger}
            aria-pressed={business.id === selectedId}
            onClick={() => onSelect(business.id)}
          >
            <span className={styles.avatar} aria-hidden="true" />
            <span className={styles.name}>{business.name}</span>
          </button>
          <span className={styles.tags}>
            <span
              className={cx(
                ui.badge,
                business.status === "active" ? ui.badgeSuccess : ui.badgeWarning,
              )}
            >
              {business.status}
            </span>
            <span className={cx(ui.badge, ui.badgeNeutral)}>{business.plan}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
