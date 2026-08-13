/**
 * platform-frontend/CLAUDE.md requires distinct, friendly copy for every failure
 * mode — never a raw error object. The exact strings are asserted here because
 * they are the entire user-facing contract of this component: a refactor that
 * collapses "rate limited" and "unavailable" into one generic message would
 * otherwise pass every other test in the suite.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatBanner } from "@/components/chat/ChatBanner";

describe("ChatBanner", () => {
  it("renders nothing when there is no banner to show", () => {
    const { container } = render(<ChatBanner banner={{ kind: "none" }} onRetry={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders distinct copy for a 429 rate-limited state", () => {
    render(<ChatBanner banner={{ kind: "rate-limited" }} onRetry={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      /you're sending messages a bit too fast\. please wait a moment and try again\./i,
    );
  });

  it("renders distinct copy for a 503 provider-unavailable state", () => {
    render(<ChatBanner banner={{ kind: "unavailable" }} onRetry={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      /the assistant is temporarily unavailable\. please try again shortly\./i,
    );
  });

  it("passes a normalized backend message straight through for a generic error", () => {
    render(
      <ChatBanner banner={{ kind: "error", message: "The server exploded" }} onRetry={vi.fn()} />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("The server exploded");
  });

  it("does not use the generic error copy for the rate-limited state", () => {
    // Guards against the three branches collapsing into one.
    render(<ChatBanner banner={{ kind: "rate-limited" }} onRetry={vi.fn()} />);

    expect(screen.getByRole("alert")).not.toHaveTextContent(/temporarily unavailable/i);
  });

  it("announces the failure assertively via role=alert", () => {
    render(<ChatBanner banner={{ kind: "unavailable" }} onRetry={vi.fn()} />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("offers a retry affordance that invokes onRetry", () => {
    const onRetry = vi.fn();
    render(<ChatBanner banner={{ kind: "rate-limited" }} onRetry={onRetry} />);

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
