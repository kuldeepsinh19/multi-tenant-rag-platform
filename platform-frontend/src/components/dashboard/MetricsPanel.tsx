import type { BusinessMetrics } from "@/api/businesses";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusMessage } from "@/components/ui/StatusMessage";
import ui from "@/styles/primitives.module.css";

import styles from "./MetricsPanel.module.css";

interface Props {
  metrics: BusinessMetrics | undefined;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | undefined;
}

/* Intl is a platform primitive — no formatting dependency needed. Raw integers
   previously rendered as e.g. "1234567", which is hard to scan. */
const integer = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const currency = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function MetricsPanel({ metrics, isLoading, isError, errorMessage }: Props) {
  if (isLoading) return <Skeleton count={5} variant="tile" label="Loading metrics…" />;
  if (isError)
    return <StatusMessage tone="error">Couldn&apos;t load metrics: {errorMessage}</StatusMessage>;
  if (!metrics) return <EmptyState title="No metrics yet." hint="Data appears after your first conversations." />;

  const stats: Array<{ label: string; value: string }> = [
    { label: "Total messages", value: integer.format(metrics.total_messages) },
    { label: "Total tokens", value: integer.format(metrics.total_tokens) },
    { label: "Total cost", value: currency.format(metrics.total_cost_usd) },
    { label: "Avg latency", value: `${integer.format(metrics.avg_latency_ms)} ms` },
    { label: "Groundedness", value: `${(metrics.groundedness_pass_rate * 100).toFixed(1)}%` },
  ];

  /* <dl> is the correct semantic for label/value pairs — a screen reader now
     associates each term with its description instead of reading loose spans. */
  return (
    <dl className={styles.grid}>
      {stats.map((stat) => (
        <div key={stat.label} className={styles.stat}>
          <dt className={ui.overline}>{stat.label}</dt>
          <dd className={styles.value}>{stat.value}</dd>
        </div>
      ))}
    </dl>
  );
}
