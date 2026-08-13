import { useState } from "react";

import { ApiError } from "@/api/client";
import { BusinessList } from "@/components/admin/BusinessList";
import { CreateBusinessForm } from "@/components/admin/CreateBusinessForm";
import { CreateWidgetKeyForm } from "@/components/admin/CreateWidgetKeyForm";
import { InviteAdminForm } from "@/components/admin/InviteAdminForm";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusMessage } from "@/components/ui/StatusMessage";
import { useBusiness } from "@/hooks/useBusiness";
import { useBusinesses } from "@/hooks/useBusinesses";
import { useCreateBusiness } from "@/hooks/useCreateBusiness";
import { useCreateWidgetKey } from "@/hooks/useCreateWidgetKey";
import { useInviteAdmin } from "@/hooks/useInviteAdmin";
import { cx } from "@/lib/cx";
import { useAuthStore } from "@/store/auth";
import ui from "@/styles/primitives.module.css";
import shell from "@/styles/shell.module.css";

function errorMessageOf(error: unknown): string | undefined {
  if (!error) return undefined;
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

/** Thin container for the super-admin surface: list/create businesses, view
 * one, invite its admin, and mint a widget key. Composes presentational
 * components from src/components/admin; all data fetching lives in hooks. */
export function SuperAdminDashboard() {
  const logout = useAuthStore((state) => state.logout);
  const businessesQuery = useBusinesses();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selectedBusinessQuery = useBusiness(selectedId ?? undefined);
  const createBusiness = useCreateBusiness();
  const inviteAdmin = useInviteAdmin(selectedId ?? "");
  const createWidgetKey = useCreateWidgetKey(selectedId ?? "");

  return (
    <>
      <a className="skip-link" href="#dashboard-content">
        Skip to content
      </a>
      <main className={shell.page}>
        <header className={shell.header}>
          <div className={shell.brand}>
            <span className={shell.mark} aria-hidden="true" />
            <h1 className={shell.brandTitle}>Super Admin</h1>
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
            <h2 className={ui.cardTitle}>Businesses</h2>
            <div className={shell.cardStack}>
              <BusinessList
                businesses={businessesQuery.data}
                isLoading={businessesQuery.isLoading}
                isError={businessesQuery.isError}
                errorMessage={errorMessageOf(businessesQuery.error)}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
              <hr className={shell.divider} />
              <CreateBusinessForm
                onCreate={(name) => createBusiness.mutate({ name })}
                isPending={createBusiness.isPending}
                errorMessage={errorMessageOf(createBusiness.error)}
              />
            </div>
          </section>

          {selectedId ? (
            <section className={cx(ui.card, shell.section)}>
              <h2 className={ui.cardTitle}>{selectedBusinessQuery.data?.name ?? "Business"}</h2>
              {selectedBusinessQuery.isLoading ? (
                <Skeleton count={1} label="Loading business…" />
              ) : null}
              {selectedBusinessQuery.isError ? (
                <StatusMessage tone="error">
                  Couldn&apos;t load business: {errorMessageOf(selectedBusinessQuery.error)}
                </StatusMessage>
              ) : null}

              <div className={shell.cardStack}>
                <InviteAdminForm
                  onInvite={(email, password) => inviteAdmin.mutate({ email, password })}
                  isPending={inviteAdmin.isPending}
                  errorMessage={errorMessageOf(inviteAdmin.error)}
                  successMessage={
                    inviteAdmin.isSuccess ? `Invited ${inviteAdmin.data.email}` : undefined
                  }
                />

                <hr className={shell.divider} />

                <CreateWidgetKeyForm
                  onCreate={(domains) => createWidgetKey.mutate({ allowed_domains: domains })}
                  isPending={createWidgetKey.isPending}
                  errorMessage={errorMessageOf(createWidgetKey.error)}
                  createdKey={createWidgetKey.data}
                />
              </div>
            </section>
          ) : null}
        </div>
      </main>
    </>
  );
}
