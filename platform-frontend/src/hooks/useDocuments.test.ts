/**
 * Document ingestion is asynchronous (Arq worker: pending -> processing ->
 * ready/failed), so the dashboard polls. The polling *stop* condition is the
 * part worth testing: if refetchInterval ever fails to return false once every
 * document has settled, the dashboard hammers the API forever for every open
 * tab. These tests drive the real refetchInterval predicate through the hook.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Document, DocumentStatus } from "@/api/documents";

const fetchDocumentsMock = vi.hoisted(() => vi.fn());

vi.mock("@/api/documents", () => ({
  fetchDocuments: fetchDocumentsMock,
}));

const { documentsQueryKey, useDocuments } = await import("@/hooks/useDocuments");

function doc(id: string, status: DocumentStatus): Document {
  return {
    id,
    business_id: "b1",
    filename: `${id}.pdf`,
    mime_type: "application/pdf",
    status,
    error: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

/** A fresh client per test so cached data never leaks between cases. */
function wrapper(): { client: QueryClient; Wrapper: (props: { children: ReactNode }) => ReactNode } {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    client,
    Wrapper: ({ children }) => createElement(QueryClientProvider, { client }, children),
  };
}

/** Re-runs the hook's own refetchInterval option against the live query state. */
function currentInterval(client: QueryClient, businessId: string): number | false {
  const query = client.getQueryCache().find({ queryKey: documentsQueryKey(businessId) });
  if (!query) throw new Error("query not found");
  // `query.options` is typed as QueryOptions, which omits refetchInterval —
  // it lives on QueryObserverOptions. The value is present at runtime, so
  // narrow through a local shape rather than widening the hook's own types.
  const option = (
    query.options as { refetchInterval?: (q: typeof query) => number | false }
  ).refetchInterval;
  if (typeof option !== "function") throw new Error("refetchInterval is not a function");
  return option(query);
}

afterEach(() => {
  fetchDocumentsMock.mockReset();
});

describe("documentsQueryKey", () => {
  it("scopes the cache entry by business id so tenants never share a key", () => {
    expect(documentsQueryKey("b1")).toEqual(["documents", "b1"]);
    expect(documentsQueryKey("b2")).not.toEqual(documentsQueryKey("b1"));
  });
});

describe("useDocuments", () => {
  it("does not fetch until a business id is known", () => {
    const { Wrapper } = wrapper();

    const { result } = renderHook(() => useDocuments(undefined), { wrapper: Wrapper });

    expect(fetchDocumentsMock).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches the tenant's documents once a business id is supplied", async () => {
    fetchDocumentsMock.mockResolvedValue([doc("d1", "ready")]);
    const { Wrapper } = wrapper();

    const { result } = renderHook(() => useDocuments("b1"), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([doc("d1", "ready")]);
    expect(fetchDocumentsMock).toHaveBeenCalledWith("b1", expect.anything());
  });

  it("keeps polling every 3s while a document is still pending", async () => {
    fetchDocumentsMock.mockResolvedValue([doc("d1", "pending")]);
    const { client, Wrapper } = wrapper();

    const { result } = renderHook(() => useDocuments("b1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(currentInterval(client, "b1")).toBe(3000);
  });

  it("keeps polling while a document is processing", async () => {
    fetchDocumentsMock.mockResolvedValue([doc("d1", "ready"), doc("d2", "processing")]);
    const { client, Wrapper } = wrapper();

    const { result } = renderHook(() => useDocuments("b1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(currentInterval(client, "b1")).toBe(3000);
  });

  it("stops polling once every document has settled into ready or failed", async () => {
    fetchDocumentsMock.mockResolvedValue([doc("d1", "ready"), doc("d2", "failed")]);
    const { client, Wrapper } = wrapper();

    const { result } = renderHook(() => useDocuments("b1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(currentInterval(client, "b1")).toBe(false);
  });

  it("stops polling when the business has no documents at all", async () => {
    fetchDocumentsMock.mockResolvedValue([]);
    const { client, Wrapper } = wrapper();

    const { result } = renderHook(() => useDocuments("b1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(currentInterval(client, "b1")).toBe(false);
  });

  it("surfaces a fetch failure to the caller instead of polling on", async () => {
    fetchDocumentsMock.mockRejectedValue(new Error("network down"));
    const { client, Wrapper } = wrapper();

    const { result } = renderHook(() => useDocuments("b1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(currentInterval(client, "b1")).toBe(false);
  });
});
