import type { ReactNode } from "react";

import { Navigate } from "@/router/router";
import { useAuthStore } from "@/store/auth";

/** Redirects to /login when unauthenticated; otherwise renders children. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuthStore((state) => state.token);
  if (!token) return <Navigate to="/login" />;
  return <>{children}</>;
}

/** Redirects to /login when unauthenticated, or to /dashboard when
 * authenticated but not a super_admin. */
export function RequireSuperAdmin({ children }: { children: ReactNode }) {
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  if (!token) return <Navigate to="/login" />;
  if (role !== "super_admin") return <Navigate to="/dashboard" />;
  return <>{children}</>;
}

/** Redirects to /login when unauthenticated, or to /admin when authenticated
 * but not a business_admin. */
export function RequireBusinessAdmin({ children }: { children: ReactNode }) {
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  if (!token) return <Navigate to="/login" />;
  if (role !== "business_admin") return <Navigate to="/admin" />;
  return <>{children}</>;
}
