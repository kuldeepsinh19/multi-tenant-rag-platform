import type { Citation } from "@/api/sse";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Only ever set on a completed assistant message. */
  citations?: Citation[];
  escalated?: boolean;
}

export type ChatBannerState =
  | { kind: "none" }
  | { kind: "error"; message: string }
  | { kind: "rate-limited" }
  | { kind: "unavailable" };
