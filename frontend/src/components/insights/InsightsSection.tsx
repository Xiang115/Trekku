import { useEffect, useMemo, useState } from "react";
import * as api from "../../api/client";
import { ApiError } from "../../api/client";
import { useCities } from "../../hooks/useRatings";
import { formatCompact, formatCurrency } from "../../lib/format";
import type { EntitySummary, EntityType, TrendResponse } from "../../api/types";
import CitySelect from "./CitySelect";
import EntitySelect from "./EntitySelect";
import MetricToggle from "./MetricToggle";
import TrendChart, { type TrendMetric } from "./TrendChart";

const ENTITY_TYPES: { value: EntityType; label: string }[] = [
  { value: "hotels", label: "Hotels" },
  { value: "attractions", label: "Attractions" },
  { value: "flights", label: "Flights" },
];

const METRICS: { value: TrendMetric; label: string }[] = [
  { value: "price_min", label: "Price" },
  { value: "rating", label: "Rating" },
  { value: "review_count", label: "Reviews" },
];

function formatMetric(metric: TrendMetric, value: number): string {
  if (metric === "price_min") return formatCurrency(value);
  if (metric === "rating") return value.toFixed(1);
  return formatCompact(value);
}

export default function InsightsSection() {
  const { cities, loading: citiesLoading, error: citiesError } = useCities();
  const [city, setCity] = useState("");
  const [entityType, setEntityType] = useState<EntityType>("hotels");
  const [entities, setEntities] = useState<EntitySummary[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [entityId, setEntityId] = useState("");
  const [metric, setMetric] = useState<TrendMetric>("price_min");
  const [metricTouched, setMetricTouched] = useState(false);
  const [trend, setTrend] = useState<TrendResponse | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendError, setTrendError] = useState<string | null>(null);

  const chooseMetric = (next: TrendMetric) => {
    setMetric(next);
    setMetricTouched(true);
  };

  // Switching entity type resets the dependent selection up front. Clearing
  // entityId here (rather than only inside the entities effect) means the trend
  // effect re-runs with an empty id and skips the fetch, instead of briefly
  // re-querying the previous type's id under the new type — which produced the
  // spurious `GET /ratings/trend/flights/hotel_… 404`. Flights only ever carry
  // price data, so default the metric back to price on every switch.
  const chooseEntityType = (next: EntityType) => {
    setEntityType(next);
    setEntityId("");
    setTrend(null);
    setTrendError(null);
    setMetric("price_min");
    setMetricTouched(false);
  };

  // Default the city once cities load.
  useEffect(() => {
    if (!city && cities.length > 0) setCity(cities[0]);
  }, [cities, city]);

  // Load entities when city or entity type changes.
  useEffect(() => {
    if (!city) return;
    let cancelled = false;
    setEntitiesLoading(true);
    setEntities([]);
    setEntityId("");
    setTrend(null);
    api
      .getEntities(entityType, city)
      .then((list) => {
        if (cancelled) return;
        setEntities(list);
        if (list.length > 0) setEntityId(list[0].entity_id);
      })
      .catch(() => {
        if (!cancelled) setEntities([]);
      })
      .finally(() => {
        if (!cancelled) setEntitiesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [city, entityType]);

  // Load trend when the selected entity changes.
  useEffect(() => {
    if (!entityId) {
      setTrend(null);
      return;
    }
    let cancelled = false;
    setTrendLoading(true);
    setTrendError(null);
    api
      .getTrend(entityType, entityId)
      .then((res) => {
        if (!cancelled) setTrend(res);
      })
      .catch((err) => {
        if (cancelled) return;
        setTrend(null);
        setTrendError(
          err instanceof ApiError && err.status === 404
            ? "No rating history recorded for this entity yet."
            : err instanceof ApiError
              ? err.message
              : "Could not load trend data.",
        );
      })
      .finally(() => {
        if (!cancelled) setTrendLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entityId, entityType]);

  // Each newly selected entity gets a sensible default metric again.
  useEffect(() => {
    setMetricTouched(false);
  }, [entityId, entityType]);

  // Auto-pick the first metric that actually has data (price → rating →
  // reviews) so the chart isn't empty just because the default metric is
  // unpopulated for this entity. A manual choice (metricTouched) is respected.
  useEffect(() => {
    if (!trend || metricTouched) return;
    const order: TrendMetric[] = ["price_min", "rating", "review_count"];
    const firstWithData = order.find((m) => trend.data.some((p) => p[m] != null));
    if (firstWithData && firstWithData !== metric) setMetric(firstWithData);
  }, [trend, metricTouched, metric]);

  const stats = useMemo(() => {
    const values = (trend?.data ?? [])
      .map((p) => p[metric])
      .filter((v): v is number => v != null);
    if (values.length === 0) return null;
    const latest = values[values.length - 1];
    const first = values[0];
    const max = Math.max(...values);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const changePct = first !== 0 ? Math.round(((latest - first) / first) * 100) : 0;
    return { latest, max, avg, changePct };
  }, [trend, metric]);

  const selectedEntityName = entities.find((e) => e.entity_id === entityId)?.name;
  const isFlights = entityType === "flights";

  // Flights only ever record a fare — no rating or review snapshots exist for
  // them — so price is the only meaningful metric. Other types may offer all
  // three. From that per-type base, only keep metrics that actually have data
  // for the loaded entity, so empty series are never shown as blank charts.
  const availableMetrics = useMemo(() => {
    const base = isFlights ? METRICS.filter((m) => m.value === "price_min") : METRICS;
    if (!trend) return base;
    const filtered = base.filter((m) => trend.data.some((p) => p[m.value] != null));
    return filtered.length > 0 ? filtered : base;
  }, [trend, isFlights]);

  return (
    <section className="section-block insights-block" id="insights">
      <div className="section-heading">
        <div>
          <p className="panel-kicker">Insight Dashboard</p>
          <h2>Price &amp; rating trends</h2>
        </div>
        <MetricToggle
          options={ENTITY_TYPES}
          value={entityType}
          onChange={chooseEntityType}
          ariaLabel="Entity type"
        />
      </div>

      {citiesError && <div className="error-note">{citiesError}</div>}

      <div className="insight-controls">
        {/* Flights always route into Selangor, so a destination-city filter is
            meaningless for them — the route (origin → Selangor) is chosen via
            the entity selector instead. */}
        {isFlights ? (
          <label className="select-field">
            Destination
            <select value="Selangor" disabled>
              <option value="Selangor">Selangor (KUL)</option>
            </select>
          </label>
        ) : (
          <CitySelect cities={cities} value={city} onChange={setCity} loading={citiesLoading} />
        )}
        <EntitySelect
          entities={entities}
          value={entityId}
          onChange={setEntityId}
          loading={entitiesLoading}
          label={isFlights ? "Route" : "Entity"}
        />
        <MetricToggle
          options={availableMetrics}
          value={metric}
          onChange={chooseMetric}
          ariaLabel="Trend metric"
        />
      </div>

      <div className="insights-grid">
        <article className="peak-month-card">
          <p className="panel-kicker">Tracking</p>
          <h3>{selectedEntityName ?? "—"}</h3>
          <strong>{isFlights ? "Flights → Selangor" : `${city} · ${entityType}`}</strong>
          <p>
            {isFlights
              ? "Historical fares captured from live flight-price snapshots."
              : `Historical ${metric.replace("_", " ")} captured from live rating snapshots.`}
          </p>
        </article>

        <article className="insight-stat-card">
          <span>Latest</span>
          <strong>{stats ? formatMetric(metric, stats.latest) : "—"}</strong>
          <small>Most recent snapshot</small>
        </article>

        <article className="insight-stat-card">
          <span>Average</span>
          <strong>{stats ? formatMetric(metric, Math.round(stats.avg * 10) / 10) : "—"}</strong>
          <small>Across recorded period</small>
        </article>

        <article className="insight-stat-card">
          <span>Change</span>
          <strong>{stats ? `${stats.changePct > 0 ? "+" : ""}${stats.changePct}%` : "—"}</strong>
          <small>First → latest snapshot</small>
        </article>
      </div>

      <div className="analytics-layout">
        <article className="chart-panel">
          <div className="chart-header">
            <div>
              <h3>{selectedEntityName ?? "Select an entity"}</h3>
              <p>{METRICS.find((m) => m.value === metric)?.label} over time</p>
            </div>
            {stats && <span className="badge green">Peak: {formatMetric(metric, stats.max)}</span>}
          </div>

          {trendLoading && (
            <div className="loading-note">
              <span className="inline-spinner" /> Loading trend…
            </div>
          )}
          {trendError && <div className="error-note">{trendError}</div>}
          {!trendLoading && !trendError && trend && (
            <TrendChart data={trend.data} metric={metric} />
          )}
          {!trendLoading && !trendError && !trend && (
            <div className="empty-state">Pick a city and entity to see its trend.</div>
          )}
        </article>

        <aside className="analysis-panel">
          <h3>How to read this</h3>
          <ul>
            <li>
              <span style={{ color: "var(--green)" }}>●</span> Bars show each recorded snapshot for
              the selected metric.
            </li>
            <li>
              <span style={{ color: "var(--coral)" }}>●</span> The highlighted bar marks the peak
              value in the series.
            </li>
            <li>
              <span style={{ color: "var(--teal)" }}>●</span> Switch metric to compare price, rating
              and review trends.
            </li>
          </ul>
        </aside>
      </div>
    </section>
  );
}
