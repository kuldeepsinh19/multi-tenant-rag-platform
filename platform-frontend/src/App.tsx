import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useThemeSync } from "@/hooks/useThemeSync";
import { BusinessAdminDashboard } from "@/pages/BusinessAdminDashboard";
import { LoginPage } from "@/pages/LoginPage";
import { RootRedirect } from "@/pages/RootRedirect";
import { SuperAdminDashboard } from "@/pages/SuperAdminDashboard";
import { RequireBusinessAdmin, RequireSuperAdmin } from "@/router/Guards";
import { Route, RouterProvider } from "@/router/router";

const queryClient = new QueryClient();

export function App() {
  // Applies the persisted theme and follows OS changes while mode is "system".
  useThemeSync();

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <RouterProvider>
          <Route path="/">
            <RootRedirect />
          </Route>
          <Route path="/login">
            <LoginPage />
          </Route>
          <Route path="/admin">
            <RequireSuperAdmin>
              <SuperAdminDashboard />
            </RequireSuperAdmin>
          </Route>
          <Route path="/dashboard">
            <RequireBusinessAdmin>
              <BusinessAdminDashboard />
            </RequireBusinessAdmin>
          </Route>
        </RouterProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
