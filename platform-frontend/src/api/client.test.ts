/**
 * The API client is the single choke point for auth headers and error shape —
 * every screen depends on it behaving identically. These tests stub `fetch`
 * itself (the one sanctioned place to do so; everywhere else mocks this module)
 * to pin three things that are easy to break in a refactor: the bearer token is
 * attached only when set, multipart uploads must NOT carry a Content-Type, and
 * a 204 must never attempt to parse a body.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  apiRequest,
  apiRequestMultipart,
  getAuthToken,
  setAuthToken,
} from "@/api/client";

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

function noContentResponse(): Response {
  return {
    ok: true,
    status: 204,
    json: () => Promise.reject(new Error("204 responses have no body to parse")),
  } as unknown as Response;
}

/** The init object fetch was called with, narrowed for assertions. */
function lastInit(): RequestInit & { headers: Record<string, string> } {
  const call = fetchMock.mock.calls[0];
  if (!call) throw new Error("fetch was not called");
  return call[1] as RequestInit & { headers: Record<string, string> };
}

function lastUrl(): string {
  const call = fetchMock.mock.calls[0];
  if (!call) throw new Error("fetch was not called");
  return String(call[0]);
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  // Module-level auth state leaks between tests otherwise.
  setAuthToken(null);
});

describe("setAuthToken / getAuthToken", () => {
  it("round-trips a token and clears back to null", () => {
    expect(getAuthToken()).toBeNull();

    setAuthToken("jwt-abc");
    expect(getAuthToken()).toBe("jwt-abc");

    setAuthToken(null);
    expect(getAuthToken()).toBeNull();
  });
});

describe("apiRequest", () => {
  it("defaults to GET, forces a JSON content type, and sends no body", async () => {
    fetchMock.mockResolvedValue(jsonResponse([{ id: "b1" }]));

    await apiRequest("/businesses");

    expect(lastUrl()).toMatch(/\/businesses$/);
    expect(lastInit().method).toBe("GET");
    expect(lastInit().headers["Content-Type"]).toBe("application/json");
    expect(lastInit().body).toBeUndefined();
  });

  it("omits the Authorization header when no token is set", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));

    await apiRequest("/health");

    expect(lastInit().headers.Authorization).toBeUndefined();
  });

  it("attaches a bearer Authorization header once a token is set", async () => {
    setAuthToken("jwt-abc");
    fetchMock.mockResolvedValue(jsonResponse({}));

    await apiRequest("/businesses");

    expect(lastInit().headers.Authorization).toBe("Bearer jwt-abc");
  });

  it("serializes the body and honours an explicit method", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "b1", name: "Acme Inc" }));

    await apiRequest("/businesses", { method: "POST", body: { name: "Acme Inc" } });

    expect(lastInit().method).toBe("POST");
    expect(lastInit().body).toBe(JSON.stringify({ name: "Acme Inc" }));
  });

  it("forwards an AbortSignal so React Query can cancel in-flight requests", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(jsonResponse({}));

    await apiRequest("/businesses", { signal: controller.signal });

    expect(lastInit().signal).toBe(controller.signal);
  });

  it("returns the parsed JSON body on success", async () => {
    fetchMock.mockResolvedValue(jsonResponse([{ id: "b1", name: "Acme Inc" }]));

    const result = await apiRequest<Array<{ id: string }>>("/businesses");

    expect(result).toEqual([{ id: "b1", name: "Acme Inc" }]);
  });

  it("returns undefined for 204 without touching the response body", async () => {
    // The 204 branch must short-circuit: DELETE /documents/{id} returns no body,
    // and calling .json() on it would reject.
    fetchMock.mockResolvedValue(noContentResponse());

    await expect(apiRequest<void>("/businesses/b1/documents/d1", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("normalizes a backend DomainError body into ApiError fields", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ error: "NotAuthorized", message: "You cannot access this business." }, 403),
    );

    await expect(apiRequest("/businesses/other")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      code: "NotAuthorized",
      message: "You cannot access this business.",
    });
  });

  it("falls back to a generic code and message when the error body is not JSON", async () => {
    const brokenBody = {
      ok: false,
      status: 502,
      json: () => Promise.reject(new SyntaxError("Unexpected token < in JSON")),
    } as unknown as Response;
    fetchMock.mockResolvedValue(brokenBody);

    await expect(apiRequest("/chat")).rejects.toMatchObject({
      status: 502,
      code: "UnknownError",
      message: "Something went wrong. Please try again.",
    });
  });

  it("throws an ApiError instance so callers can instanceof-narrow it", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ error: "RateLimited", message: "Slow down." }, 429));

    await expect(apiRequest("/chat")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("apiRequestMultipart", () => {
  it("posts FormData without a Content-Type header so the browser sets the boundary", async () => {
    // Setting Content-Type here would strip the multipart boundary and the
    // backend's `file` field would never parse.
    const formData = new FormData();
    formData.append("file", new File(["hello"], "handbook.txt", { type: "text/plain" }));
    fetchMock.mockResolvedValue(jsonResponse({ id: "d1", filename: "handbook.txt" }));

    await apiRequestMultipart("/businesses/b1/documents", formData);

    expect(lastInit().method).toBe("POST");
    expect(lastInit().headers["Content-Type"]).toBeUndefined();
    expect(lastInit().body).toBe(formData);
  });

  it("attaches the same bearer token as apiRequest", async () => {
    setAuthToken("jwt-abc");
    fetchMock.mockResolvedValue(jsonResponse({ id: "d1" }));

    await apiRequestMultipart("/businesses/b1/documents", new FormData());

    expect(lastInit().headers.Authorization).toBe("Bearer jwt-abc");
  });

  it("normalizes upload errors through the same ApiError path", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ error: "UnsupportedUploadType", message: "That file type isn't supported." }, 422),
    );

    await expect(
      apiRequestMultipart("/businesses/b1/documents", new FormData()),
    ).rejects.toMatchObject({ status: 422, code: "UnsupportedUploadType" });
  });
});
