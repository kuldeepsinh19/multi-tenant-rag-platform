/**
 * The auth store is the only thing keeping API calls authenticated: it mirrors
 * the JWT into the api client's module-level token on every transition. The
 * rehydration path (onRehydrateStorage) is the subtle one — without it a page
 * refresh restores the store from localStorage but leaves the api client
 * tokenless, and every request silently 401s. That case is covered explicitly.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const setAuthTokenMock = vi.hoisted(() => vi.fn());

vi.mock("@/api/client", () => ({
  setAuthToken: setAuthTokenMock,
}));

// Imported after the mock so the store binds the spy.
const { useAuthStore } = await import("@/store/auth");

const STORAGE_KEY = "platform-auth";

beforeEach(() => {
  useAuthStore.setState({ token: null, role: null, businessId: null });
  setAuthTokenMock.mockClear();
});

afterEach(() => {
  localStorage.clear();
  vi.resetModules();
});

describe("useAuthStore", () => {
  it("starts logged out", () => {
    const state = useAuthStore.getState();

    expect(state.token).toBeNull();
    expect(state.role).toBeNull();
    expect(state.businessId).toBeNull();
  });

  it("login sets state and arms the api client token in one step", () => {
    useAuthStore.getState().login({ token: "jwt-abc", role: "business_admin", businessId: "b1" });

    expect(useAuthStore.getState()).toMatchObject({
      token: "jwt-abc",
      role: "business_admin",
      businessId: "b1",
    });
    expect(setAuthTokenMock).toHaveBeenCalledWith("jwt-abc");
  });

  it("login for a super-admin stores a null businessId", () => {
    // Super-admins are not scoped to a tenant; the backend issues a JWT whose
    // business_id claim is null (src/auth/security.py::create_access_token).
    useAuthStore.getState().login({ token: "jwt-super", role: "super_admin", businessId: null });

    expect(useAuthStore.getState().role).toBe("super_admin");
    expect(useAuthStore.getState().businessId).toBeNull();
  });

  it("logout clears every field and disarms the api client token", () => {
    useAuthStore.getState().login({ token: "jwt-abc", role: "business_admin", businessId: "b1" });
    setAuthTokenMock.mockClear();

    useAuthStore.getState().logout();

    expect(useAuthStore.getState()).toMatchObject({
      token: null,
      role: null,
      businessId: null,
    });
    expect(setAuthTokenMock).toHaveBeenCalledWith(null);
  });

  it("persists exactly token, role and businessId — and nothing else", () => {
    useAuthStore.getState().login({ token: "jwt-abc", role: "business_admin", businessId: "b1" });

    const raw = localStorage.getItem(STORAGE_KEY);
    expect(raw).not.toBeNull();
    // Actions must never be serialized, and no password or secret may appear.
    expect(JSON.parse(raw as string).state).toEqual({
      token: "jwt-abc",
      role: "business_admin",
      businessId: "b1",
    });
  });

  it("re-arms the api client token when the store rehydrates from localStorage", async () => {
    // Simulates a page refresh: storage already holds a session, and a freshly
    // imported store module must push that token back into the api client.
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        state: { token: "jwt-restored", role: "business_admin", businessId: "b1" },
        version: 0,
      }),
    );
    setAuthTokenMock.mockClear();
    vi.resetModules();

    const { useAuthStore: rehydrated } = await import("@/store/auth");

    expect(rehydrated.getState().token).toBe("jwt-restored");
    expect(setAuthTokenMock).toHaveBeenCalledWith("jwt-restored");
  });

  it("rehydrates to a null token when storage is empty", async () => {
    localStorage.clear();
    setAuthTokenMock.mockClear();
    vi.resetModules();

    const { useAuthStore: rehydrated } = await import("@/store/auth");

    expect(rehydrated.getState().token).toBeNull();
    expect(setAuthTokenMock).toHaveBeenCalledWith(null);
  });
});
