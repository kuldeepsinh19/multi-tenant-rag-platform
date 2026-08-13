import { parseSseChunk, type ChatStreamEvent } from "./sse";

export interface WidgetChatConfig {
  apiBase: string;
  publicKey: string;
}

export class WidgetChatError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "WidgetChatError";
  }
}

/**
 * POSTs to {apiBase}/widget/chat with the X-Widget-Key header (no JWT — the
 * widget is unauthenticated end-user surface, gated only by the public key),
 * and streams the SSE response with the same wire shape as the dashboard's
 * /chat endpoint.
 */
export async function streamWidgetChat(
  config: WidgetChatConfig,
  message: string,
  conversationId: string | undefined,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${config.apiBase}/widget/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Widget-Key": config.publicKey,
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      error?: string;
      message?: string;
    };
    throw new WidgetChatError(
      response.status,
      body.message ?? "Something went wrong. Please try again.",
    );
  }

  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseChunk(buffer);
    buffer = rest;
    for (const event of events) onEvent(event);
  }
}
