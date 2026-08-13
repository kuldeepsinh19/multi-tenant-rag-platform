import { Navigate } from "@/router/router";
import { useAuthStore } from "@/store/auth";

/** Root `/` redirects based on auth state: unauthenticated -> /login,
 * super_admin -> /admin, business_admin -> /dashboard. */
export function RootRedirect() {
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);

  if (!token) return <Navigate to="/login" />;
  if (role === "super_admin") return <Navigate to="/admin" />;
  return <Navigate to="/dashboard" />;
}
