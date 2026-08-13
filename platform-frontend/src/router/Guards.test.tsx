/**
 * These guards are the client-side half of the super-admin / business-admin
 * split. They are NOT a security boundary — the backend derives business_id from
 * the JWT and re-checks the role on every request — but a guard that silently
 * stops redirecting would show a business admin the super-admin console shell,
 * which is a serious trust and UX failure. Every role/route combination is
 * enumerated so no branch can rot unnoticed.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { RequireAuth, RequireBusinessAdmin, RequireSuperAdmin } from "@/router/Guards";
import { RouterProvider } from "@/router/router";
import { useAuthStore } from "@/store/auth";

function renderGuarded(guard: React.ReactElement) {
  return render(<RouterProvider>{guard}</RouterProvider>);
}

function signIn(role: "super_admin" | "business_admin"): void {
  useAuthStore.setState({
    token: "jwt-abc",
    role,
    businessId: role === "business_admin" ? "b1" : null,
  });
}

beforeEach(() => {
  window.history.pushState(null, "", "/");
  useAuthStore.setState({ token: null, role: null, businessId: null });
});

afterEach(() => {
  useAuthStore.setState({ token: null, role: null, businessId: null });
});

describe("RequireAuth", () => {
  it("redirects an anonymous visitor to the login page", async () => {
    renderGuarded(
      <RequireAuth>
        <p>protected</p>
      </RequireAuth>,
    );

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
    expect(screen.queryByText("protected")).not.toBeInTheDocument();
  });

  it("renders children for any authenticated role", () => {
    signIn("business_admin");

    renderGuarded(
      <RequireAuth>
        <p>protected</p>
      </RequireAuth>,
    );

    expect(screen.getByText("protected")).toBeInTheDocument();
  });
});

describe("RequireSuperAdmin", () => {
  it("redirects an anonymous visitor to the login page", async () => {
    renderGuarded(
      <RequireSuperAdmin>
        <p>admin console</p>
      </RequireSuperAdmin>,
    );

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
    expect(screen.queryByText("admin console")).not.toBeInTheDocument();
  });

  it("bounces a business admin to their own dashboard", async () => {
    signIn("business_admin");

    renderGuarded(
      <RequireSuperAdmin>
        <p>admin console</p>
      </RequireSuperAdmin>,
    );

    await waitFor(() => expect(window.location.pathname).toBe("/dashboard"));
    // The critical assertion: the privileged shell must never render, even for
    // the frame before the redirect lands.
    expect(screen.queryByText("admin console")).not.toBeInTheDocument();
  });

  it("renders the console for a super admin", () => {
    signIn("super_admin");

    renderGuarded(
      <RequireSuperAdmin>
        <p>admin console</p>
      </RequireSuperAdmin>,
    );

    expect(screen.getByText("admin console")).toBeInTheDocument();
  });
});

describe("RequireBusinessAdmin", () => {
  it("redirects an anonymous visitor to the login page", async () => {
    renderGuarded(
      <RequireBusinessAdmin>
        <p>tenant dashboard</p>
      </RequireBusinessAdmin>,
    );

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
    expect(screen.queryByText("tenant dashboard")).not.toBeInTheDocument();
  });

  it("bounces a super admin to the admin console", async () => {
    signIn("super_admin");

    renderGuarded(
      <RequireBusinessAdmin>
        <p>tenant dashboard</p>
      </RequireBusinessAdmin>,
    );

    await waitFor(() => expect(window.location.pathname).toBe("/admin"));
    expect(screen.queryByText("tenant dashboard")).not.toBeInTheDocument();
  });

  it("renders the dashboard for a business admin", () => {
    signIn("business_admin");

    renderGuarded(
      <RequireBusinessAdmin>
        <p>tenant dashboard</p>
      </RequireBusinessAdmin>,
    );

    expect(screen.getByText("tenant dashboard")).toBeInTheDocument();
  });

  it("redirects when a role is present but the token has been cleared", async () => {
    // Defensive: logout() nulls both, but a partially-cleared store must fail
    // closed rather than render a tenant's data.
    useAuthStore.setState({ token: null, role: "business_admin", businessId: "b1" });

    renderGuarded(
      <RequireBusinessAdmin>
        <p>tenant dashboard</p>
      </RequireBusinessAdmin>,
    );

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
  });
});
