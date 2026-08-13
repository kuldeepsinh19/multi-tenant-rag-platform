import type { Document } from "@/api/documents";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusMessage } from "@/components/ui/StatusMessage";
import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./DocumentList.module.css";

interface Props {
  documents: Document[] | undefined;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | undefined;
  onDelete: (documentId: string) => void;
  deletingId: string | undefined;
}

const statusBadge: Record<string, string | undefined> = {
  ready: ui.badgeSuccess,
  processing: ui.badgeInfo,
  pending: ui.badgeWarning,
  failed: ui.badgeDanger,
};

export function DocumentList({
  documents,
  isLoading,
  isError,
  errorMessage,
  onDelete,
  deletingId,
}: Props) {
  if (isLoading) return <Skeleton count={3} label="Loading documents…" />;
  if (isError)
    return (
      <StatusMessage tone="error">Couldn&apos;t load documents: {errorMessage}</StatusMessage>
    );
  if (!documents || documents.length === 0)
    return (
      <EmptyState
        title="No documents uploaded yet."
        hint="Upload a document above to give your chatbot something to ground its answers in."
      />
    );

  return (
    <ul className={styles.list}>
      {documents.map((doc) => (
        <li key={doc.id} className={styles.item}>
          <span className={styles.name} title={doc.filename}>
            {doc.filename}
          </span>

          <span className={cx(ui.badge, statusBadge[doc.status], styles.status)}>
            {doc.status}
          </span>

          <button
            type="button"
            className={cx(ui.btn, ui.btnDanger, ui.btnSm, styles.delete)}
            onClick={() => onDelete(doc.id)}
            disabled={deletingId === doc.id}
          >
            {deletingId === doc.id ? "Deleting…" : "Delete"}
          </button>

          {/* Its own grid row spanning the full width. Previously this carried
              role="alert" and inherited the global alert block styling, which
              injected a padded red box into the middle of a flex row and broke
              the layout. The role stays; the presentation is now local. */}
          {doc.status === "failed" && doc.error ? (
            <span className={styles.error} role="alert">
              {doc.error}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
