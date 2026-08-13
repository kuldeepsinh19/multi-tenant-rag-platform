/**
 * StatusMessage exists because ARIA roles were previously doing double duty as
 * styling hooks. Its contract is that the role is derived from intent (errors
 * interrupt, everything else is polite) and can always be overridden — those
 * defaults are what every call site in the app silently relies on.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusMessage } from "@/components/ui/StatusMessage";

describe("StatusMessage — default role", () => {
  it("uses the assertive alert role for errors", () => {
    render(<StatusMessage tone="error">Something failed</StatusMessage>);

    expect(screen.getByRole("alert")).toHaveTextContent("Something failed");
  });

  it("uses the polite status role for success", () => {
    render(<StatusMessage tone="success">Admin invited</StatusMessage>);

    expect(screen.getByRole("status")).toHaveTextContent("Admin invited");
  });

  it("uses the polite status role for info", () => {
    render(<StatusMessage tone="info">Processing</StatusMessage>);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("uses the polite status role for warning", () => {
    // Deliberate: a warning should not interrupt a screen reader mid-sentence.
    render(<StatusMessage tone="warning">Nearly at your limit</StatusMessage>);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

describe("StatusMessage — overrides", () => {
  it("lets a caller downgrade an error to a polite status", () => {
    render(
      <StatusMessage tone="error" role="status">
        Recoverable
      </StatusMessage>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Recoverable");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("lets a caller upgrade a non-error to an assertive alert", () => {
    render(
      <StatusMessage tone="warning" role="alert">
        Act now
      </StatusMessage>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Act now");
  });
});

describe("StatusMessage — presentation", () => {
  it("hides its decorative icon from assistive tech", () => {
    const { container } = render(<StatusMessage tone="error">Failed</StatusMessage>);

    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });

  it("appends a caller-supplied className alongside its own", () => {
    render(
      <StatusMessage tone="info" className="custom-spacing">
        Note
      </StatusMessage>,
    );

    expect(screen.getByRole("status")).toHaveClass("custom-spacing");
  });

  it("renders rich children, not just strings", () => {
    render(
      <StatusMessage tone="info">
        Couldn&apos;t load documents: <strong>timeout</strong>
      </StatusMessage>,
    );

    expect(screen.getByText("timeout").tagName).toBe("STRONG");
  });
});
