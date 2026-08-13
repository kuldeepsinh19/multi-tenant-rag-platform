/**
 * streamChat is the transport half of the chat feature: it wires fetch's
 * ReadableStream into parseSseChunk and fans events out to the UI. The bug this
 * guards against is a token boundary landing mid-frame — so the chunks below are
 * split at deliberately awkward byte offsets rather than on frame boundaries.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, setAuthToken } from "@/api/client";
import { streamChat } from "@/api/chat";
import type { ChatStreamEvent } from "@/api/sse";

const fetchMock = vi.fn();
const encoder = new TextEncoder();

/**
 * A minimal stand-in for response.body — streamChat only ever calls
 * getReader().read(), so a hand-rolled reader keeps the test deterministic and
 * free of any real stream scheduling.
 */
function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  let index = 0;
  const reader = {
    read: () =>
      index < chunks.length
        ? Promise.resolve({ done: false, value: encoder.encode(chunks[index++]) })
        : Promise.resolve({ done: true, value: undefined }),
  };
  return { getReader: () => reader } as unknown as ReadableStream<Uint8Array>;
}

function streamingResponse(chunks: string[]): Response {
  return { ok: true, status: 200, body: streamOf(chunks) } as unknown as Response;
}

function lastInit(): RequestInit & { headers: Record<string, string> } {
  const call = fetchMock.mock.calls[0];
  if (!call) throw new Error("fetch was not called");
  return call[1] as RequestInit & { headers: Record<string, string> };
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  setAuthToken(null);
});

describe("streamChat", () => {
  it("POSTs the chat payload to /chat as JSON", async () => {
    fetchMock.mockResolvedValue(streamingResponse([]));

    await streamChat({ business_id: "b1", message: "What is the refund policy?" }, () => {});

    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/chat$/);
    expect(lastInit().method).toBe("POST");
    expect(lastInit().headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(String(lastInit().body))).toEqual({
      business_id: "b1",
      message: "What is the refund policy?",
    });
  });

  it("attaches the bearer token from the shared api client", async () => {
    setAuthToken("jwt-abc");
    fetchMock.mockResolvedValue(streamingResponse([]));

    await streamChat({ business_id: "b1", message: "hi" }, () => {});

    expect(lastInit().headers.Authorization).toBe("Bearer jwt-abc");
  });

  it("emits token events in order, then the done event with citations", async () => {
    fetchMock.mockResolvedValue(
      streamingResponse([
        'data: {"token":"Refunds "}\n\n',
        'data: {"token":"take 30 days."}\n\n',
        'data: {"done":true,"citations":[{"doc_id":"d1","title":"handbook.pdf"}]}\n\n',
      ]),
    );

    const events: ChatStreamEvent[] = [];
    await streamChat({ business_id: "b1", message: "refunds?" }, (event) => events.push(event));

    expect(events).toEqual([
      { token: "Refunds " },
      { token: "take 30 days." },
      { done: true, citations: [{ doc_id: "d1", title: "handbook.pdf" }] },
    ]);
  });

  it("reassembles a frame split across two network chunks", async () => {
    // The whole reason the parser returns a `rest` tail.
    fetchMock.mockResolvedValue(
      streamingResponse(['data: {"token":"split', ' across"}\n\n']),
    );

    const events: ChatStreamEvent[] = [];
    await streamChat({ business_id: "b1", message: "hi" }, (event) => events.push(event));

    expect(events).toEqual([{ token: "split across" }]);
  });

  it("handles several frames delivered in a single chunk", async () => {
    fetchMock.mockResolvedValue(
      streamingResponse(['data: {"token":"a"}\n\ndata: {"token":"b"}\n\n']),
    );

    const events: ChatStreamEvent[] = [];
    await streamChat({ business_id: "b1", message: "hi" }, (event) => events.push(event));

    expect(events).toEqual([{ token: "a" }, { token: "b" }]);
  });

  it("throws a normalized ApiError when the backend rejects before streaming", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({ error: "RateLimitExceeded", message: "Too many requests." }),
    } as unknown as Response);

    await expect(
      streamChat({ business_id: "b1", message: "hi" }, () => {}),
    ).rejects.toMatchObject({ status: 429, code: "RateLimitExceeded" });
  });

  it("throws an ApiError with generic copy when the error body is unparseable", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.reject(new SyntaxError("not json")),
    } as unknown as Response);

    const error = await streamChat({ business_id: "b1", message: "hi" }, () => {}).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 503,
      code: "UnknownError",
      message: "Something went wrong. Please try again.",
    });
  });

  it("returns quietly when the response carries no body", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, body: null } as unknown as Response);

    const onEvent = vi.fn();
    await expect(
      streamChat({ business_id: "b1", message: "hi" }, onEvent),
    ).resolves.toBeUndefined();
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("forwards the abort signal so the UI stop button can cancel the stream", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(streamingResponse([]));

    await streamChat({ business_id: "b1", message: "hi" }, () => {}, controller.signal);

    expect(lastInit().signal).toBe(controller.signal);
  });

  // KNOWN GAP: an unterminated trailing frame is dropped (the final `rest` is
  // never flushed, and the TextDecoder is never flushed either). Harmless while
  // the backend always terminates with a done frame; recorded so a change in
  // that contract surfaces here.
  it("drops a trailing frame that never received its terminator", async () => {
    fetchMock.mockResolvedValue(streamingResponse(['data: {"token":"lost"}']));

    const events: ChatStreamEvent[] = [];
    await streamChat({ business_id: "b1", message: "hi" }, (event) => events.push(event));

    expect(events).toEqual([]);
  });
});
