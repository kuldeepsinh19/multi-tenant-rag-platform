/**
 * This component renders untrusted LLM output as HTML. That makes it the single
 * highest-risk render in the frontend: a poisoned document could get a payload
 * into an assistant answer, and the only thing standing between that and stored
 * XSS is the DOMPurify call at ChatMessageList.tsx:90. The sanitization tests
 * below are the reason this file exists; the rest pin the accessibility
 * affordances (aria-live, real "Sources" text) that grounded answers depend on.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatMessageList } from "@/components/chat/ChatMessageList";
import type { ChatMessage } from "@/components/chat/types";

function userMessage(content: string): ChatMessage {
  return { id: "u1", role: "user", content };
}

function assistantMessage(content: string, extra: Partial<ChatMessage> = {}): ChatMessage {
  return { id: "a1", role: "assistant", content, ...extra };
}

describe("ChatMessageList — sanitization", () => {
  it("strips a script tag from assistant output", () => {
    const { container } = render(
      <ChatMessageList
        messages={[assistantMessage('Refunds take 30 days.<script>window.__pwned = true;</script>')]}
        isStreaming={false}
      />,
    );

    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/refunds take 30 days/i)).toBeInTheDocument();
  });

  it("strips an inline event handler from assistant output", () => {
    const { container } = render(
      <ChatMessageList
        messages={[assistantMessage('<img src="x" onerror="window.__pwned = true">')]}
        isStreaming={false}
      />,
    );

    expect(container.querySelector("img")?.getAttribute("onerror")).toBeNull();
  });

  it("strips a javascript: href from assistant output", () => {
    const { container } = render(
      <ChatMessageList
        messages={[assistantMessage('<a href="javascript:alert(1)">click me</a>')]}
        isStreaming={false}
      />,
    );

    // DOMPurify drops the attribute outright rather than rewriting it, so
    // assert on the absence of any javascript: link rather than on the value.
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(screen.getByText("click me")).toBeInTheDocument();
  });

  it("keeps benign formatting markup in assistant output", () => {
    // Sanitizing must not mean stripping everything — grounded answers render
    // markdown-ish emphasis and lists.
    const { container } = render(
      <ChatMessageList
        messages={[assistantMessage("<p>Refunds take <strong>30 days</strong>.</p>")]}
        isStreaming={false}
      />,
    );

    expect(container.querySelector("strong")).not.toBeNull();
  });

  it("renders user content as text, never as markup", () => {
    const { container } = render(
      <ChatMessageList
        messages={[userMessage("<script>alert(1)</script>")]}
        isStreaming={false}
      />,
    );

    expect(container.querySelector("script")).toBeNull();
    // React escapes it, so the literal source text is visible instead.
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
  });
});

describe("ChatMessageList — states", () => {
  it("renders the empty state when there are no messages", () => {
    render(<ChatMessageList messages={[]} isStreaming={false} />);

    expect(screen.getByText(/no messages yet/i)).toBeInTheDocument();
    expect(screen.getByText(/ask a question to get started/i)).toBeInTheDocument();
  });

  it("labels each turn with its speaker", () => {
    render(
      <ChatMessageList
        messages={[userMessage("What is the refund policy?"), assistantMessage("30 days.")]}
        isStreaming={false}
      />,
    );

    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("Assistant")).toBeInTheDocument();
  });

  it("announces new messages politely without stealing focus", () => {
    render(<ChatMessageList messages={[assistantMessage("hi")]} isStreaming={false} />);

    const list = screen.getByRole("list");
    expect(list).toHaveAttribute("aria-live", "polite");
    expect(list).toHaveAttribute("aria-relevant", "additions text");
  });

  it("shows the typing indicator while streaming and hides it afterwards", () => {
    const { rerender, container } = render(
      <ChatMessageList messages={[assistantMessage("partial")]} isStreaming />,
    );
    // The indicator is decorative, so it is aria-hidden rather than announced.
    expect(container.querySelector('li[aria-hidden="true"]')).not.toBeNull();

    rerender(<ChatMessageList messages={[assistantMessage("complete")]} isStreaming={false} />);

    expect(container.querySelector('li[aria-hidden="true"]')).toBeNull();
  });
});

describe("ChatMessageList — citations", () => {
  it("renders each citation title under a real Sources label", () => {
    render(
      <ChatMessageList
        messages={[
          assistantMessage("Refunds take 30 days.", {
            citations: [
              { doc_id: "d1", title: "handbook.pdf" },
              { doc_id: "d2", title: "policy.md" },
            ],
          }),
        ]}
        isStreaming={false}
      />,
    );

    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("handbook.pdf")).toBeInTheDocument();
    expect(screen.getByText("policy.md")).toBeInTheDocument();
  });

  it("omits the Sources block entirely when the answer has no citations", () => {
    // An ungrounded-but-fine answer is normal; an empty "Sources" heading would
    // imply attribution that does not exist.
    render(
      <ChatMessageList
        messages={[assistantMessage("I don't have that in your documents.", { citations: [] })]}
        isStreaming={false}
      />,
    );

    expect(screen.queryByText("Sources")).not.toBeInTheDocument();
  });

  it("omits the Sources block when citations are undefined", () => {
    render(
      <ChatMessageList messages={[assistantMessage("streaming…")]} isStreaming />,
    );

    expect(screen.queryByText("Sources")).not.toBeInTheDocument();
  });
});

describe("ChatMessageList — escalation", () => {
  it("announces the escalation notice as a status region", () => {
    render(
      <ChatMessageList
        messages={[assistantMessage("Let me get someone.", { escalated: true })]}
        isStreaming={false}
      />,
    );

    const status = screen.getByRole("status");
    expect(within(status).getByText(/escalated to a human agent/i)).toBeInTheDocument();
  });

  it("does not render the escalation notice on a normal answer", () => {
    render(
      <ChatMessageList
        messages={[assistantMessage("Refunds take 30 days.", { escalated: false })]}
        isStreaming={false}
      />,
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
