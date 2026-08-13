import { ApiError, API_BASE_URL_VALUE, getAuthToken } from "@/api/client";
import { parseSseChunk, type ChatStreamEvent } from "@/api/sse";

export interface ChatRequest {
  business_id: string;
  message: string;
  conversation_id?: string;
}

/**
 * Sanctioned exception to the apiRequest-only rule: SSE streaming cannot go
 * through the JSON helper (it needs a ReadableStream reader, not a single
 * JSON body read). Uses the same auth token and error normalization as
 * apiRequest for consistency.
 */
export async function streamChat(
  payload: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAuthToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL_VALUE}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      body.error ?? "UnknownError",
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
