/**
 * Login is the one place a credential is handled, so two things are pinned here:
 * the password field must never be a plain-text input, and a failed login must
 * render the backend's deliberately non-enumerating message ("Invalid email or
 * password.") rather than anything that distinguishes unknown-email from
 * wrong-password. The api module is mocked, never fetch.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { RouterProvider } from "@/router/router";
import { useAuthStore } from "@/store/auth";

const loginMock = vi.hoisted(() => vi.fn());

vi.mock("@/api/auth", () => ({
  login: loginMock,
}));

// Imported after the mock so useLogin binds the stub.
const { LoginPage } = await import("@/pages/LoginPage");

function renderLogin(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <RouterProvider>{children}</RouterProvider>
    </QueryClientProvider>
  );
  render(<LoginPage />, { wrapper: Wrapper });
}

function fillCredentials(email: string, password: string): void {
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: email } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: password } });
}

function submit(): void {
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
}

beforeEach(() => {
  window.history.pushState(null, "", "/login");
  useAuthStore.setState({ token: null, role: null, businessId: null });
});

afterEach(() => {
  loginMock.mockReset();
  useAuthStore.setState({ token: null, role: null, businessId: null });
});

describe("LoginPage — form", () => {
  it("renders labeled email and password inputs", () => {
    renderLogin();

    expect(screen.getByLabelText(/email/i)).toHaveAttribute("id", "login-email");
    expect(screen.getByLabelText(/password/i)).toHaveAttribute("id", "login-password");
  });

  it("masks the password field", () => {
    renderLogin();

    expect(screen.getByLabelText(/password/i)).toHaveAttribute("type", "password");
  });

  it("submits the typed credentials to the api client", async () => {
    loginMock.mockResolvedValue({
      access_token: "jwt-abc",
      token_type: "bearer",
      role: "business_admin",
      business_id: "b1",
    });
    renderLogin();

    fillCredentials("admin@acme.test", "supersecret");
    submit();

    await waitFor(() =>
      expect(loginMock).toHaveBeenCalledWith({
        email: "admin@acme.test",
        password: "supersecret",
      }),
    );
  });
});

describe("LoginPage — success", () => {
  it("stores the session returned by the backend", async () => {
    loginMock.mockResolvedValue({
      access_token: "jwt-abc",
      token_type: "bearer",
      role: "business_admin",
      business_id: "b1",
    });
    renderLogin();

    fillCredentials("admin@acme.test", "supersecret");
    submit();

    await waitFor(() => {
      expect(useAuthStore.getState()).toMatchObject({
        token: "jwt-abc",
        role: "business_admin",
        businessId: "b1",
      });
    });
  });

  it("stores a null businessId for a super admin", async () => {
    loginMock.mockResolvedValue({
      access_token: "jwt-super",
      token_type: "bearer",
      role: "super_admin",
      business_id: null,
    });
    renderLogin();

    fillCredentials("super@platform.test", "supersecret");
    submit();

    await waitFor(() => {
      expect(useAuthStore.getState().role).toBe("super_admin");
    });
    expect(useAuthStore.getState().businessId).toBeNull();
  });
});

describe("LoginPage — failure", () => {
  it("renders the backend's non-enumerating message on bad credentials", async () => {
    loginMock.mockRejectedValue(
      new ApiError(401, "NotAuthenticated", "Invalid email or password."),
    );
    renderLogin();

    fillCredentials("admin@acme.test", "wrong");
    submit();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Invalid email or password.");
    });
  });

  it("falls back to generic copy when the failure is not an ApiError", async () => {
    loginMock.mockRejectedValue(new TypeError("Failed to fetch"));
    renderLogin();

    fillCredentials("admin@acme.test", "supersecret");
    submit();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/something went wrong/i);
    });
    expect(screen.getByRole("alert")).not.toHaveTextContent(/failed to fetch/i);
  });

  it("leaves the user signed out after a failed attempt", async () => {
    loginMock.mockRejectedValue(
      new ApiError(401, "NotAuthenticated", "Invalid email or password."),
    );
    renderLogin();

    fillCredentials("admin@acme.test", "wrong");
    submit();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(useAuthStore.getState().token).toBeNull();
  });
});

describe("LoginPage — already authenticated", () => {
  it("bounces a signed-in super admin to the admin console", async () => {
    useAuthStore.setState({ token: "jwt-abc", role: "super_admin", businessId: null });

    renderLogin();

    await waitFor(() => expect(window.location.pathname).toBe("/admin"));
  });

  it("bounces a signed-in business admin to their dashboard", async () => {
    useAuthStore.setState({ token: "jwt-abc", role: "business_admin", businessId: "b1" });

    renderLogin();

    await waitFor(() => expect(window.location.pathname).toBe("/dashboard"));
  });

  // KNOWN GAP: the bounce keys off `role` alone without checking `token`, so a
  // partially-cleared store redirects away from the very page needed to sign
  // back in. Documented rather than fixed.
  it("currently bounces on a stale role even with no token", async () => {
    useAuthStore.setState({ token: null, role: "super_admin", businessId: null });

    renderLogin();

    await waitFor(() => expect(window.location.pathname).toBe("/admin"));
  });
});
