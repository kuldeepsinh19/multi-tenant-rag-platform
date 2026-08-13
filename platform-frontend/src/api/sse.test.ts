/**
 * parseSseChunk is the hardest piece of client logic in the app: it runs on a
 * *growing* buffer fed by a network reader, so it must correctly hand back the
 * unparsed tail of a frame that hasn't fully arrived yet. Getting the carry-over
 * wrong silently truncates or duplicates assistant tokens, which is exactly the
 * class of bug that never shows up in a fast local test and always shows up on a
 * slow connection. These tests drive it the way the reader in src/api/chat.ts
 * does, one chunk at a time.
 */

import { describe, expect, it } from "vitest";

import { isDoneEvent, parseSseChunk, type ChatStreamEvent } from "@/api/sse";

function frame(payload: unknown): string {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

describe("parseSseChunk", () => {
  it("parses a single complete token frame and leaves an empty tail", () => {
    const { events, rest } = parseSseChunk(frame({ token: "Hello" }));

    expect(events).toEqual([{ token: "Hello" }]);
    expect(rest).toBe("");
  });

  it("parses several frames arriving in one chunk, preserving order", () => {
    const buffer = frame({ token: "Our " }) + frame({ token: "refund " }) + frame({ token: "policy" });

    const { events, rest } = parseSseChunk(buffer);

    expect(events).toEqual([{ token: "Our " }, { token: "refund " }, { token: "policy" }]);
    expect(rest).toBe("");
  });

  it("returns no events and holds the whole buffer when the frame is not terminated", () => {
    const { events, rest } = parseSseChunk('data: {"token":"par');

    expect(events).toEqual([]);
    expect(rest).toBe('data: {"token":"par');
  });

  it("carries a split frame across chunks and emits it once the terminator arrives", () => {
    // Exactly how streamChat drives it: buffer = rest + next decoded chunk.
    const first = parseSseChunk('data: {"token":"Hel');
    expect(first.events).toEqual([]);

    const second = parseSseChunk(first.rest + 'lo"}\n\n');

    expect(second.events).toEqual([{ token: "Hello" }]);
    expect(second.rest).toBe("");
  });

  it("emits complete frames while retaining a trailing partial one", () => {
    const buffer = frame({ token: "done" }) + 'data: {"token":"partia';

    const { events, rest } = parseSseChunk(buffer);

    expect(events).toEqual([{ token: "done" }]);
    expect(rest).toBe('data: {"token":"partia');
  });

  it("parses the terminal done frame with its citations", () => {
    const { events } = parseSseChunk(
      frame({ done: true, citations: [{ doc_id: "d1", title: "handbook.pdf" }] }),
    );

    expect(events).toEqual([
      { done: true, citations: [{ doc_id: "d1", title: "handbook.pdf" }] },
    ]);
  });

  it("skips a malformed frame instead of throwing, so one hiccup cannot kill the stream", () => {
    const buffer = "data: {not json at all}\n\n" + frame({ token: "survived" });

    const { events } = parseSseChunk(buffer);

    expect(events).toEqual([{ token: "survived" }]);
  });

  it("skips a frame whose data payload is empty", () => {
    const { events } = parseSseChunk("data:\n\n" + frame({ token: "kept" }));

    expect(events).toEqual([{ token: "kept" }]);
  });

  it("ignores a frame with no data: line at all (comments, keep-alives)", () => {
    const { events } = parseSseChunk(": keep-alive\n\n" + frame({ token: "kept" }));

    expect(events).toEqual([{ token: "kept" }]);
  });

  it("finds the data: line when preceded by event:/id: metadata lines", () => {
    const buffer = `event: message\nid: 7\ndata: ${JSON.stringify({ token: "meta" })}\n\n`;

    const { events } = parseSseChunk(buffer);

    expect(events).toEqual([{ token: "meta" }]);
  });

  it("tolerates a data: line with no space after the colon", () => {
    const { events } = parseSseChunk('data:{"token":"tight"}\n\n');

    expect(events).toEqual([{ token: "tight" }]);
  });

  it("returns nothing for an empty buffer", () => {
    expect(parseSseChunk("")).toEqual({ events: [], rest: "" });
  });

  it("preserves whitespace inside token payloads exactly", () => {
    // Token frames carry their own leading/trailing spaces — trimming them would
    // silently glue words together in the rendered answer.
    const { events } = parseSseChunk(frame({ token: "  spaced  " }));

    expect(events).toEqual([{ token: "  spaced  " }]);
  });

  // KNOWN GAP: the parser splits on "\n\n" only. A proxy that rewrites line
  // endings to CRLF would produce frames this never emits. Documented rather
  // than fixed — the current backend (src/chat/service.py::_sse) emits "\n\n".
  it("does not currently split CRLF-delimited frames", () => {
    const { events, rest } = parseSseChunk('data: {"token":"crlf"}\r\n\r\n');

    expect(events).toEqual([]);
    expect(rest).toBe('data: {"token":"crlf"}\r\n\r\n');
  });

  // KNOWN GAP: only the first data: line of a frame is read, so a multi-line
  // data continuation (valid per the SSE spec) drops everything after line one.
  it("reads only the first data: line of a multi-line frame", () => {
    const { events } = parseSseChunk('data: {"token":"first"}\ndata: {"token":"second"}\n\n');

    expect(events).toEqual([{ token: "first" }]);
  });
});

describe("isDoneEvent", () => {
  it("narrows a done frame", () => {
    const event: ChatStreamEvent = { done: true, citations: [] };

    expect(isDoneEvent(event)).toBe(true);
  });

  it("rejects a token frame", () => {
    const event: ChatStreamEvent = { token: "hi" };

    expect(isDoneEvent(event)).toBe(false);
  });

  it("rejects an object that carries done but not done === true", () => {
    // Guards against a backend regression sending done:false as a heartbeat —
    // that must not terminate the message on the client.
    const event = { done: false } as unknown as ChatStreamEvent;

    expect(isDoneEvent(event)).toBe(false);
  });
});
