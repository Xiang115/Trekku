import { formatCompact, formatCurrency, formatShortDate } from "../../lib/format";
import type { TrendPoint } from "../../api/types";

export type TrendMetric = "price_min" | "rating" | "review_count";

function formatValue(metric: TrendMetric, value: number): string {
  if (metric === "price_min") return formatCurrency(value);
  if (metric === "rating") return value.toFixed(1);
  return formatCompact(value);
}

export default function TrendChart({
  data,
  metric,
}: {
  data: TrendPoint[];
  metric: TrendMetric;
}) {
  const points = data.map((p) => ({ date: p.date, value: p[metric] }));
  const numericValues = points.map((p) => p.value).filter((v): v is number => v != null);

  if (numericValues.length === 0) {
    return <div className="empty-state">No {metric.replace("_", " ")} data for this entity.</div>;
  }

  const max = Math.max(...numericValues);
  const peakIndex = points.findIndex((p) => p.value === max);

  return (
    <div className="bar-chart trend" aria-label="Trend chart">
      {points.map((p, index) => {
        const height = p.value == null ? 12 : Math.max(12, Math.round((p.value / max) * 230));
        const isPeak = index === peakIndex ? " is-peak" : "";
        return (
          <div key={`${p.date}-${index}`} className={`month-bar${isPeak}`}>
            <button
              type="button"
              style={{ "--height": `${height}px` } as React.CSSProperties}
              data-value={p.value == null ? "n/a" : formatValue(metric, p.value)}
              aria-label={`${formatShortDate(p.date)}: ${p.value == null ? "no data" : formatValue(metric, p.value)}`}
            />
            <span>{formatShortDate(p.date)}</span>
            <small>{p.value == null ? "—" : formatValue(metric, p.value)}</small>
          </div>
        );
      })}
    </div>
  );
}
