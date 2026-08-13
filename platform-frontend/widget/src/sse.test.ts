/**
 * The widget's SSE parser is a deliberate copy of the dashboard's (see the
 * header comment in ./sse.ts — the widget is an independent build target and
 * must not import app source). Deliberate duplication is only safe if drift is
 * detectable, so this file does two things: it re-runs the parser matrix against
 * the widget's own copy, and it asserts byte-for-byte agreement between the two
 * implementations across every fixture.
 *
 * Lives under widget/ rather than src/ so the root tsconfig (include: ["src"])
 * never pulls widget code into the app's typecheck. Imports are relative for
 * the same reason — the "@" alias points at src/ and is off-limits here.
 */

import { describe, expect, it } from "vitest";

import { isDoneEvent, parseSseChunk, type ChatStreamEvent } from "./sse";
import {
  parseSseChunk as parseSseChunkApp,
  type ChatStreamEvent as AppChatStreamEvent,
} from "../../src/api/sse";

function frame(payload: unknown): string {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

/** Every buffer shape both parsers must agree on. */
const FIXTURES: Array<{ name: string; buffer: string }> = [
  { name: "empty buffer", buffer: "" },
  { name: "single token frame", buffer: frame({ token: "Hello" }) },
  {
    name: "multiple frames in one chunk",
    buffer: frame({ token: "a" }) + frame({ token: "b" }) + frame({ token: "c" }),
  },
  { name: "unterminated frame", buffer: 'data: {"token":"par' },
  {
    name: "complete frame plus a partial tail",
    buffer: frame({ token: "done" }) + 'data: {"token":"partia',
  },
  {
    name: "done frame with citations",
    buffer: frame({ done: true, citations: [{ doc_id: "d1", title: "handbook.pdf" }] }),
  },
  { name: "done frame with escalation", buffer: frame({ done: true, citations: [], escalated: true }) },
  { name: "malformed json", buffer: "data: {not json}\n\n" + frame({ token: "survived" }) },
  { name: "empty data payload", buffer: "data:\n\n" + frame({ token: "kept" }) },
  { name: "comment line only", buffer: ": keep-alive\n\n" + frame({ token: "kept" }) },
  {
    name: "event and id metadata lines",
    buffer: `event: message\nid: 7\ndata: ${JSON.stringify({ token: "meta" })}\n\n`,
  },
  { name: "no space after data colon", buffer: 'data:{"token":"tight"}\n\n' },
  { name: "whitespace-significant token", buffer: frame({ token: "  spaced  " }) },
  { name: "crlf delimited", buffer: 'data: {"token":"crlf"}\r\n\r\n' },
  {
    name: "multi-line data continuation",
    buffer: 'data: {"token":"first"}\ndata: {"token":"second"}\n\n',
  },
];

describe("widget parseSseChunk", () => {
  it("parses a single complete token frame", () => {
    const { events, rest } = parseSseChunk(frame({ token: "Hello" }));

    expect(events).toEqual([{ token: "Hello" }]);
    expect(rest).toBe("");
  });

  it("carries a split frame across chunks", () => {
    const first = parseSseChunk('data: {"token":"Hel');
    const second = parseSseChunk(first.rest + 'lo"}\n\n');

    expect(second.events).toEqual([{ token: "Hello" }]);
  });

  it("parses the done frame with citations", () => {
    const { events } = parseSseChunk(
      frame({ done: true, citations: [{ doc_id: "d1", title: "handbook.pdf" }] }),
    );

    expect(events).toEqual([
      { done: true, citations: [{ doc_id: "d1", title: "handbook.pdf" }] },
    ]);
  });

  it("skips malformed frames instead of throwing", () => {
    const { events } = parseSseChunk("data: {broken}\n\n" + frame({ token: "survived" }));

    expect(events).toEqual([{ token: "survived" }]);
  });

  it("returns nothing for an empty buffer", () => {
    expect(parseSseChunk("")).toEqual({ events: [], rest: "" });
  });
});

describe("widget isDoneEvent", () => {
  it("narrows a done frame", () => {
    const event: ChatStreamEvent = { done: true, citations: [] };

    expect(isDoneEvent(event)).toBe(true);
  });

  it("rejects a token frame", () => {
    const event: ChatStreamEvent = { token: "hi" };

    expect(isDoneEvent(event)).toBe(false);
  });
});

describe("drift guard: widget parser vs dashboard parser", () => {
  it.each(FIXTURES)("agrees on $name", ({ buffer }) => {
    const widgetResult = parseSseChunk(buffer);
    const appResult = parseSseChunkApp(buffer);

    expect(widgetResult.events).toEqual(appResult.events as ChatStreamEvent[]);
    expect(widgetResult.rest).toBe(appResult.rest);
  });

  it("agrees on the done-event predicate", () => {
    // Structural, not nominal: the two ChatStreamEvent types are separate
    // declarations, so the cast documents that they must stay compatible.
    const done: ChatStreamEvent = { done: true, citations: [] };
    const token: ChatStreamEvent = { token: "hi" };

    expect(isDoneEvent(done)).toBe(true);
    expect(isDoneEvent(token)).toBe(false);
    // If the app's event shape ever diverges, this assignment stops compiling.
    const asApp: AppChatStreamEvent = done;
    expect(asApp).toEqual(done);
  });
});
