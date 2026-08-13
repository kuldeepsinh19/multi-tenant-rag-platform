import { useState } from "react";

import { ApiError } from "@/api/client";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { DocumentList } from "@/components/dashboard/DocumentList";
import { DocumentUploadForm } from "@/components/dashboard/DocumentUploadForm";
import { EmbedSnippet } from "@/components/dashboard/EmbedSnippet";
import { MetricsPanel } from "@/components/dashboard/MetricsPanel";
import { ThemeToggle } from "@/components/ThemeToggle";
import { StatusMessage } from "@/components/ui/StatusMessage";
import { useDeleteDocument } from "@/hooks/useDeleteDocument";
import { useDocuments } from "@/hooks/useDocuments";
import { useMetrics } from "@/hooks/useMetrics";
import { useUploadDocument } from "@/hooks/useUploadDocument";
import { cx } from "@/lib/cx";
import { useAuthStore } from "@/store/auth";
import ui from "@/styles/primitives.module.css";
import shell from "@/styles/shell.module.css";

function errorMessageOf(error: unknown): string | undefined {
  if (!error) return undefined;
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

const API_BASE = import.meta.env.VITE_API_BASE_URL;

/** Thin container for the business-admin surface: document management with
 * live status polling, embed snippet, a test-chat panel, and metrics. */
export function BusinessAdminDashboard() {
  const businessId = useAuthStore((state) => state.businessId);
  const logout = useAuthStore((state) => state.logout);
  const [lastPublicKey, setLastPublicKey] = useState<string | undefined>(undefined);
  const [deletingId, setDeletingId] = useState<string | undefined>(undefined);

  const documentsQuery = useDocuments(businessId ?? undefined);
  const uploadDocument = useUploadDocument(businessId ?? "");
  const deleteDocument = useDeleteDocument(businessId ?? "");
  const metricsQuery = useMetrics(businessId ?? undefined);

  if (!businessId) {
    return (
      <main className={shell.page}>
        <StatusMessage tone="error">No business associated with this account.</StatusMessage>
      </main>
    );
  }

  const handleDelete = (documentId: string) => {
    setDeletingId(documentId);
    deleteDocument.mutate(documentId, { onSettled: () => setDeletingId(undefined) });
  };

  return (
    <>
      <a className="skip-link" href="#dashboard-content">
        Skip to content
      </a>
      <main className={shell.page}>
        <header className={shell.header}>
          <div className={shell.brand}>
            <span className={shell.mark} aria-hidden="true" />
            <h1 className={shell.brandTitle}>Business Dashboard</h1>
          </div>
          <div className={shell.headerActions}>
            <ThemeToggle />
            {/* aria-label carries the name at every width — below 30rem the
                visible text collapses and only the icon remains. */}
            <button
              type="button"
              className={cx(ui.btn, ui.btnGhost)}
              onClick={logout}
              aria-label="Log out"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                <path
                  d="M15 4.5H6.5A1.5 1.5 0 0 0 5 6v12a1.5 1.5 0 0 0 1.5 1.5H15"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <path
                  d="M13.5 12h6.5m0 0-2.5-2.5M20 12l-2.5 2.5"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span className={shell.logoutLabel}>Log out</span>
            </button>
          </div>
        </header>

        <div id="dashboard-content" className={shell.content} tabIndex={-1}>
          <section className={cx(ui.card, shell.section)}>
            <h2 className={ui.cardTitle}>Documents</h2>
            <div className={shell.cardStack}>
              <DocumentUploadForm
                onUpload={(file) => uploadDocument.mutate(file)}
                isPending={uploadDocument.isPending}
                errorMessage={errorMessageOf(uploadDocument.error)}
              />
              <DocumentList
                documents={documentsQuery.data}
                isLoading={documentsQuery.isLoading}
                isError={documentsQuery.isError}
                errorMessage={errorMessageOf(documentsQuery.error)}
                onDelete={handleDelete}
                deletingId={deletingId}
              />
            </div>
          </section>

          <section className={cx(ui.card, shell.section)}>
            <h2 className={ui.cardTitle}>Embed widget</h2>
            <div className={shell.cardStack}>
              <EmbedSnippet publicKey={lastPublicKey} apiBase={API_BASE} />
              <div className={ui.field}>
                <label className={ui.label} htmlFor="manual-public-key">
                  Public key
                </label>
                <input
                  id="manual-public-key"
                  className={cx(ui.input, ui.inputMono)}
                  value={lastPublicKey ?? ""}
                  onChange={(event) => setLastPublicKey(event.target.value || undefined)}
                  placeholder="pk_…"
                  aria-describedby="manual-public-key-hint"
                />
                <p id="manual-public-key-hint" className={ui.hint}>
                  Create a widget key from the super admin console, then paste its public key
                  here to preview the snippet.
                </p>
              </div>
            </div>
          </section>

          <section className={cx(ui.card, shell.section)}>
            <h2 className={ui.cardTitle}>Test chat</h2>
            <ChatPanel businessId={businessId} />
          </section>

          <section className={cx(ui.card, shell.section)}>
            <h2 className={ui.cardTitle}>Metrics</h2>
            <MetricsPanel
              metrics={metricsQuery.data}
              isLoading={metricsQuery.isLoading}
              isError={metricsQuery.isError}
              errorMessage={errorMessageOf(metricsQuery.error)}
            />
          </section>
        </div>
      </main>
    </>
  );
}
