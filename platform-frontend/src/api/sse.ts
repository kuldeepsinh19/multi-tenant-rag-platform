/**
 * Shared SSE event shapes + a small pure parsing helper for the chat streaming
 * endpoints (/chat and /widget/chat share the same wire format). Kept pure
 * (no fetch, no React) so it's trivially unit-testable and safe to duplicate
 * into the standalone widget bundle without pulling in app code.
 */

export interface Citation {
  doc_id: string;
  title: string;
}

export interface ChatTokenEvent {
  token: string;
}

export interface ChatDoneEvent {
  done: true;
  citations: Citation[];
  /**
   * Id of the conversation this turn belongs to. The server creates the
   * conversation, so this frame is the only way the client can learn the id
   * and continue the same thread on the next turn. Null on a guardrail-blocked
   * turn (nothing is persisted for one) — callers must keep their existing id
   * rather than overwrite it with null.
   */
  conversation_id?: string | null;
  /**
   * True when the agent gave up and escalated to a human, so the UI can render
   * a distinct state. Empty citations alone is a normal ungrounded-but-fine
   * answer, not an escalation — we do not infer escalation from it.
   */
  escalated?: boolean;
}

export type ChatStreamEvent = ChatTokenEvent | ChatDoneEvent;

export function isDoneEvent(event: ChatStreamEvent): event is ChatDoneEvent {
  return "done" in event && event.done === true;
}

/**
 * Splits a growing SSE text buffer on blank-line-delimited events, parses each
 * `data: {...}` payload as JSON, and returns the parsed events found plus the
 * remaining unparsed buffer tail (a partial event that hasn't arrived in full
 * yet). Malformed lines are skipped rather than throwing, since a stream
 * hiccup shouldn't crash the whole render.
 */
export function parseSseChunk(buffer: string): { events: ChatStreamEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: ChatStreamEvent[] = [];

  for (const part of parts) {
    const line = part
      .split("\n")
      .find((candidate) => candidate.startsWith("data:"));
    if (!line) continue;

    const jsonText = line.slice("data:".length).trim();
    if (!jsonText) continue;

    try {
      events.push(JSON.parse(jsonText) as ChatStreamEvent);
    } catch {
      // Skip malformed event rather than aborting the whole stream.
      continue;
    }
  }

  return { events, rest };
}
