/**
 * The composer is the only input path into the agent, so its guards matter:
 * blank sends must never reach the backend (they would burn a rate-limit slot
 * and a guardrail rejection), and Enter-vs-Shift+Enter is the keyboard contract
 * users rely on. Focus return after send is an accessibility requirement, not a
 * nicety — keyboard users otherwise lose their place after every message.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatComposer } from "@/components/chat/ChatComposer";

interface Overrides {
  disabled?: boolean;
  isStreaming?: boolean;
}

function renderComposer(overrides: Overrides = {}) {
  const onSend = vi.fn();
  const onStop = vi.fn();
  render(
    <ChatComposer
      onSend={onSend}
      onStop={onStop}
      disabled={false}
      isStreaming={false}
      {...overrides}
    />,
  );
  return { onSend, onStop };
}

function input(): HTMLTextAreaElement {
  return screen.getByLabelText(/message/i) as HTMLTextAreaElement;
}

function type(text: string): void {
  fireEvent.change(input(), { target: { value: text } });
}

describe("ChatComposer — sending", () => {
  it("sends the typed message when Send is clicked", () => {
    const { onSend } = renderComposer();

    type("What is the refund policy?");
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSend).toHaveBeenCalledWith("What is the refund policy?");
  });

  it("trims surrounding whitespace before sending", () => {
    const { onSend } = renderComposer();

    type("   spaced out   ");
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSend).toHaveBeenCalledWith("spaced out");
  });

  it("clears the input after a successful send", () => {
    renderComposer();

    type("first question");
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(input().value).toBe("");
  });

  it("returns focus to the input after sending", () => {
    renderComposer();

    type("first question");
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(document.activeElement).toBe(input());
  });
});

describe("ChatComposer — keyboard", () => {
  it("sends on Enter", () => {
    const { onSend } = renderComposer();

    type("via keyboard");
    fireEvent.keyDown(input(), { key: "Enter" });

    expect(onSend).toHaveBeenCalledWith("via keyboard");
  });

  it("does not send on Shift+Enter, leaving the value intact for a newline", () => {
    const { onSend } = renderComposer();

    type("line one");
    fireEvent.keyDown(input(), { key: "Enter", shiftKey: true });

    expect(onSend).not.toHaveBeenCalled();
    expect(input().value).toBe("line one");
  });

  it("ignores other keys", () => {
    const { onSend } = renderComposer();

    type("not yet");
    fireEvent.keyDown(input(), { key: "a" });

    expect(onSend).not.toHaveBeenCalled();
  });
});

describe("ChatComposer — guards", () => {
  it("never sends an empty message", () => {
    const { onSend } = renderComposer();

    fireEvent.keyDown(input(), { key: "Enter" });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("never sends a whitespace-only message", () => {
    const { onSend } = renderComposer();

    type("     ");
    fireEvent.keyDown(input(), { key: "Enter" });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables Send while the input is blank", () => {
    renderComposer();

    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("enables Send once there is real content", () => {
    renderComposer();

    type("ready");

    expect(screen.getByRole("button", { name: /send/i })).toBeEnabled();
  });

  it("disables both the input and Send while disabled", () => {
    renderComposer({ disabled: true });

    expect(input()).toBeDisabled();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("does not send on Enter while disabled", () => {
    const { onSend } = renderComposer({ disabled: true });

    type("queued");
    fireEvent.keyDown(input(), { key: "Enter" });

    expect(onSend).not.toHaveBeenCalled();
  });
});

describe("ChatComposer — stop control", () => {
  it("hides Stop when not streaming", () => {
    renderComposer({ isStreaming: false });

    expect(screen.queryByRole("button", { name: /stop/i })).not.toBeInTheDocument();
  });

  it("shows Stop while streaming and wires it to onStop", () => {
    const { onStop } = renderComposer({ isStreaming: true });

    fireEvent.click(screen.getByRole("button", { name: /stop/i }));

    expect(onStop).toHaveBeenCalledTimes(1);
  });
});

describe("ChatComposer — accessibility", () => {
  it("labels the input and links it to the keyboard hint", () => {
    renderComposer();

    expect(input()).toHaveAttribute("id", "chat-message-input");
    expect(input()).toHaveAttribute("aria-describedby", "chat-composer-hint");
    expect(document.getElementById("chat-composer-hint")).not.toBeNull();
  });
});
