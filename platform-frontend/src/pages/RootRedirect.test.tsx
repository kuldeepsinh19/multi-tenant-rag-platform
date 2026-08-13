/**
 * RootRedirect decides where "/" sends each kind of principal. It is the first
 * thing every user hits, and a wrong branch here dumps a business admin onto a
 * route their guard immediately bounces them off — an infinite-feeling redirect
 * loop. All three cases are enumerated.
 */

import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { RootRedirect } from "@/pages/RootRedirect";
import { RouterProvider } from "@/router/router";
import { useAuthStore } from "@/store/auth";

function renderAtRoot() {
  return render(
    <RouterProvider>
      <RootRedirect />
    </RouterProvider>,
  );
}

beforeEach(() => {
  window.history.pushState(null, "", "/");
  useAuthStore.setState({ token: null, role: null, businessId: null });
});

afterEach(() => {
  useAuthStore.setState({ token: null, role: null, businessId: null });
});

describe("RootRedirect", () => {
  it("sends an anonymous visitor to the login page", async () => {
    renderAtRoot();

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
  });

  it("sends a super admin to the admin console", async () => {
    useAuthStore.setState({ token: "jwt-abc", role: "super_admin", businessId: null });

    renderAtRoot();

    await waitFor(() => expect(window.location.pathname).toBe("/admin"));
  });

  it("sends a business admin to their tenant dashboard", async () => {
    useAuthStore.setState({ token: "jwt-abc", role: "business_admin", businessId: "b1" });

    renderAtRoot();

    await waitFor(() => expect(window.location.pathname).toBe("/dashboard"));
  });

  it("prioritises the missing token over any stale role", async () => {
    // Token is the authority — a leftover role must not grant a landing route.
    useAuthStore.setState({ token: null, role: "super_admin", businessId: null });

    renderAtRoot();

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
  });
});
