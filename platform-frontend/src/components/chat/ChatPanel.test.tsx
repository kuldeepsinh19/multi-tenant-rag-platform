import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import type { ChatStreamEvent } from "@/api/sse";

const streamChatMock = vi.hoisted(() => vi.fn());

vi.mock("@/api/chat", () => ({
  streamChat: streamChatMock,
}));

// Imported after the mock so ChatPanel picks up the mocked streamChat.
const { ChatPanel } = await import("@/components/chat/ChatPanel");

function sendMessage(text: string): void {
  const input = screen.getByLabelText(/message/i);
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
}

afterEach(() => {
  streamChatMock.mockReset();
});

describe("ChatPanel", () => {
  it("renders an empty state when there are no messages yet", () => {
    streamChatMock.mockResolvedValue(undefined);
    render(<ChatPanel businessId="biz-1" />);

    expect(screen.getByText(/no messages yet/i)).toBeInTheDocument();
  });

  it("sends a message and renders the streamed assistant reply as tokens arrive", async () => {
    streamChatMock.mockImplementation(
      async (_payload: unknown, onEvent: (event: ChatStreamEvent) => void) => {
        onEvent({ token: "Hello" });
        onEvent({ token: " there" });
        onEvent({ done: true, citations: [{ doc_id: "d1", title: "Doc One" }] });
      },
    );

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("Hi assistant");

    expect(screen.getByText("Hi assistant")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Hello there")).toBeInTheDocument();
    });
    expect(screen.getByText("Doc One")).toBeInTheDocument();
  });

  it("renders a friendly message on a network/server error", async () => {
    streamChatMock.mockImplementation(async () => {
      throw new ApiError(500, "InternalError", "The server exploded");
    });

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("Hi assistant");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("The server exploded");
    });
  });

  it("renders a distinct friendly message for a 429 rate-limited error", async () => {
    streamChatMock.mockImplementation(async () => {
      throw new ApiError(429, "RateLimited", "Too many requests");
    });

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("Hi assistant");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/sending messages a bit too fast/i);
    });
  });

  it("renders a distinct friendly message when the provider is unavailable (503)", async () => {
    streamChatMock.mockImplementation(async () => {
      throw new ApiError(503, "ProviderUnavailable", "All providers failed");
    });

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("Hi assistant");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/temporarily unavailable/i);
    });
  });

  it("falls back to generic copy when the failure is not an ApiError", async () => {
    // A transport-level failure (DNS, offline) must never leak a raw Error
    // message into the UI.
    streamChatMock.mockImplementation(async () => {
      throw new TypeError("Failed to fetch");
    });

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("Hi assistant");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/something went wrong while talking/i);
    });
    expect(screen.getByRole("alert")).not.toHaveTextContent(/failed to fetch/i);
  });

  it("renders the escalated-to-human state when the done frame reports it", async () => {
    // The fifth UI state platform-frontend/CLAUDE.md mandates. The backend does
    // not emit `escalated` today; the client handles it defensively, so this
    // pins the contract before it ships.
    streamChatMock.mockImplementation(
      async (_payload: unknown, onEvent: (event: ChatStreamEvent) => void) => {
        onEvent({ token: "Let me get someone." });
        onEvent({ done: true, citations: [], escalated: true });
      },
    );

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("I need a human");

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/escalated to a human agent/i);
    });
  });

  it("does not render the escalation notice on a normal completed answer", async () => {
    streamChatMock.mockImplementation(
      async (_payload: unknown, onEvent: (event: ChatStreamEvent) => void) => {
        onEvent({ token: "Refunds take 30 days." });
        onEvent({ done: true, citations: [] });
      },
    );

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("refunds?");

    await waitFor(() => {
      expect(screen.getByText("Refunds take 30 days.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("keeps partial content and shows no banner when the user stops the stream", async () => {
    // A user-initiated abort is not an error — surfacing a banner for it would
    // read as a failure the user caused deliberately. Driven through the real
    // Stop button so the component's own AbortController is what fires.
    streamChatMock.mockImplementation(
      (_payload: unknown, onEvent: (event: ChatStreamEvent) => void, signal?: AbortSignal) => {
        onEvent({ token: "Partial answer" });
        return new Promise((_resolve, reject) => {
          signal?.addEventListener("abort", () => {
            reject(new DOMException("The user aborted a request.", "AbortError"));
          });
        });
      },
    );

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("long question");

    await waitFor(() => {
      expect(screen.getByText("Partial answer")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /stop/i }));

    // Partial content survives, and the abort is not reported as a failure.
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /stop/i })).not.toBeInTheDocument();
    });
    expect(screen.getByText("Partial answer")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("sends the message again when the user retries after a failure", async () => {
    streamChatMock.mockImplementationOnce(async () => {
      throw new ApiError(503, "ProviderUnavailable", "down");
    });

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("retry me");

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    streamChatMock.mockImplementationOnce(
      async (_payload: unknown, onEvent: (event: ChatStreamEvent) => void) => {
        onEvent({ token: "Second time lucky." });
        onEvent({ done: true, citations: [] });
      },
    );
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Second time lucky.")).toBeInTheDocument();
    });
    expect(streamChatMock).toHaveBeenCalledTimes(2);
    // KNOWN GAP: retry re-enters runStream, which re-appends the user bubble,
    // so the same question now appears twice. Asserted so the duplicate is
    // visible in the suite rather than discovered in production.
    expect(screen.getAllByText("retry me")).toHaveLength(2);
  });

  it("derives the request payload from the businessId prop", async () => {
    streamChatMock.mockResolvedValue(undefined);

    render(<ChatPanel businessId="biz-42" />);

    sendMessage("scoped question");

    await waitFor(() => expect(streamChatMock).toHaveBeenCalled());
    expect(streamChatMock.mock.calls[0]?.[0]).toMatchObject({
      business_id: "biz-42",
      message: "scoped question",
    });
  });
});

describe("ChatPanel conversation continuity", () => {
  it("adopts the server's conversation_id and sends it on the next turn", async () => {
    // Before the backend returned conversation_id the client had no way to learn it, so
    // every turn silently started a new thread and follow-up questions lost their context.
    streamChatMock.mockImplementation(
      async (_payload: unknown, onEvent: (event: ChatStreamEvent) => void) => {
        onEvent({ token: "ok" });
        onEvent({ done: true, citations: [], conversation_id: "conv-abc" });
      },
    );

    render(<ChatPanel businessId="biz-1" />);

    sendMessage("first");
    await waitFor(() => expect(streamChatMock).toHaveBeenCalledTimes(1));
    expect(streamChatMock.mock.calls[0]?.[0]).toMatchObject({ conversation_id: undefined });

    sendMessage("second");
    await waitFor(() => expect(streamChatMock).toHaveBeenCalledTimes(2));
    expect(streamChatMock.mock.calls[1]?.[0]).toMatchObject({ conversation_id: "conv-abc" });
  });

  it("keeps the existing conversation_id when a blocked turn returns null", async () => {
    // A guardrail-blocked turn persists nothing and sends conversation_id: null.
    // Overwriting the stored id with null would drop the user out of their own thread.
    streamChatMock.mockImplementation(
      async (_payload: unknown, onEvent: (event: ChatStreamEvent) => void) => {
        onEvent({ done: true, citations: [], conversation_id: "conv-xyz" });
      },
    );
    render(<ChatPanel businessId="biz-1" />);
    sendMessage("first");
    await waitFor(() => expect(streamChatMock).toHaveBeenCalledTimes(1));

    streamChatMock.mockImplementation(
      async (_payload: unknown, onEvent: (event: ChatStreamEvent) => void) => {
        onEvent({ done: true, citations: [], conversation_id: null });
      },
    );
    sendMessage("blocked");
    await waitFor(() => expect(streamChatMock).toHaveBeenCalledTimes(2));

    sendMessage("third");
    await waitFor(() => expect(streamChatMock).toHaveBeenCalledTimes(3));
    expect(streamChatMock.mock.calls[2]?.[0]).toMatchObject({ conversation_id: "conv-xyz" });
  });
});
