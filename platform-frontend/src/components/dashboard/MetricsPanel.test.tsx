/**
 * Metrics are the tenant's only view of what their chatbot costs and how well it
 * is grounded, so the formatting has to be right — a raw 0.87 rendered where
 * "87.0%" belongs reads as a broken dashboard. Assertions use regex rather than
 * exact strings because Intl.NumberFormat is locale-sensitive and the CI locale
 * is not pinned.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BusinessMetrics } from "@/api/businesses";
import { MetricsPanel } from "@/components/dashboard/MetricsPanel";

function metrics(overrides: Partial<BusinessMetrics> = {}): BusinessMetrics {
  return {
    total_messages: 1234,
    total_tokens: 987654,
    total_cost_usd: 12.5,
    avg_latency_ms: 1850,
    groundedness_pass_rate: 0.87,
    ...overrides,
  };
}

function renderPanel(overrides: Partial<Parameters<typeof MetricsPanel>[0]> = {}) {
  render(
    <MetricsPanel
      metrics={metrics()}
      isLoading={false}
      isError={false}
      errorMessage={undefined}
      {...overrides}
    />,
  );
}

/** Reads the <dd> paired with a given <dt> label in the metrics description list. */
function valueFor(label: string): string {
  const term = screen.getByText(label);
  const value = term.parentElement?.querySelector("dd");
  if (!value) throw new Error(`no value rendered for "${label}"`);
  return value.textContent ?? "";
}

describe("MetricsPanel — render states", () => {
  it("shows a loading skeleton while fetching", () => {
    renderPanel({ isLoading: true, metrics: undefined });

    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText(/loading metrics/i)).toBeInTheDocument();
  });

  it("shows the reason when metrics fail to load", () => {
    renderPanel({ isError: true, errorMessage: "Request timed out", metrics: undefined });

    expect(screen.getByRole("alert")).toHaveTextContent(/couldn't load metrics/i);
    expect(screen.getByRole("alert")).toHaveTextContent("Request timed out");
  });

  it("shows an empty state before the first conversation", () => {
    renderPanel({ metrics: undefined });

    expect(screen.getByText(/no metrics yet/i)).toBeInTheDocument();
  });
});

describe("MetricsPanel — formatting", () => {
  it("labels every stat", () => {
    renderPanel();

    expect(screen.getByText("Total messages")).toBeInTheDocument();
    expect(screen.getByText("Total tokens")).toBeInTheDocument();
    expect(screen.getByText("Total cost")).toBeInTheDocument();
    expect(screen.getByText("Avg latency")).toBeInTheDocument();
    expect(screen.getByText("Groundedness")).toBeInTheDocument();
  });

  it("renders groundedness as a one-decimal percentage", () => {
    renderPanel({ metrics: metrics({ groundedness_pass_rate: 0.87 }) });

    expect(screen.getByText("87.0%")).toBeInTheDocument();
  });

  it("renders a perfect groundedness rate as 100.0%", () => {
    renderPanel({ metrics: metrics({ groundedness_pass_rate: 1 }) });

    expect(screen.getByText("100.0%")).toBeInTheDocument();
  });

  it("groups large integers rather than printing a raw number", () => {
    renderPanel({ metrics: metrics({ total_tokens: 987654 }) });

    // The grouping separator is locale-dependent (comma, period, or a narrow
    // no-break space), so assert the intent instead of a literal string: the
    // digits are all present, but not as one undelimited run.
    const value = valueFor("Total tokens");
    expect(value.replace(/\D/g, "")).toBe("987654");
    expect(value).not.toBe("987654");
  });

  it("renders cost with two decimal places", () => {
    renderPanel({ metrics: metrics({ total_cost_usd: 12.5 }) });

    expect(screen.getByText(/12\.50/)).toBeInTheDocument();
  });

  it("appends the unit to average latency", () => {
    renderPanel({ metrics: metrics({ avg_latency_ms: 1850 }) });

    expect(screen.getByText(/ms$/)).toBeInTheDocument();
  });

  it("renders a zeroed-out business without crashing", () => {
    renderPanel({
      metrics: metrics({
        total_messages: 0,
        total_tokens: 0,
        total_cost_usd: 0,
        avg_latency_ms: 0,
        groundedness_pass_rate: 0,
      }),
    });

    expect(screen.getByText("0.0%")).toBeInTheDocument();
  });

  it("associates each label with its value using a description list", () => {
    const { container } = render(
      <MetricsPanel
        metrics={metrics()}
        isLoading={false}
        isError={false}
        errorMessage={undefined}
      />,
    );

    expect(container.querySelector("dl")).not.toBeNull();
    expect(container.querySelectorAll("dt")).toHaveLength(5);
    expect(container.querySelectorAll("dd")).toHaveLength(5);
  });
});
