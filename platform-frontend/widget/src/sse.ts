/**
 * SSE event shapes + a small pure parsing helper for /widget/chat.
 *
 * Deliberately duplicated from platform-frontend/src/api/sse.ts rather than
 * imported: the widget is an independent build target (its own
 * package.json/tsconfig/vite config) that must never depend on the main
 * app's source tree — sharing a module across the two would either couple
 * their builds or force publishing an internal package for ~30 lines of
 * logic. Small, clear duplication here beats that coupling.
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
  /** Server-assigned conversation id; null on a guardrail-blocked turn (nothing
   * is persisted for one), so callers must not overwrite an existing id with null. */
  conversation_id?: string | null;
  escalated?: boolean;
}

export type ChatStreamEvent = ChatTokenEvent | ChatDoneEvent;

export function isDoneEvent(event: ChatStreamEvent): event is ChatDoneEvent {
  return "done" in event && event.done === true;
}

export function parseSseChunk(buffer: string): { events: ChatStreamEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: ChatStreamEvent[] = [];

  for (const part of parts) {
    const line = part.split("\n").find((candidate) => candidate.startsWith("data:"));
    if (!line) continue;

    const jsonText = line.slice("data:".length).trim();
    if (!jsonText) continue;

    try {
      events.push(JSON.parse(jsonText) as ChatStreamEvent);
    } catch {
      continue;
    }
  }

  return { events, rest };
}
