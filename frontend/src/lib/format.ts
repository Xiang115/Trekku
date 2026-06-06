/** MYR currency formatter, ported from the original prototype. */
export const formatCurrency = (value: number): string =>
  new Intl.NumberFormat("en-MY", {
    style: "currency",
    currency: "MYR",
    maximumFractionDigits: 0,
  }).format(value);

/** Compact number formatter (e.g. 12.5K) for large counts. */
export const formatCompact = (value: number): string =>
  new Intl.NumberFormat("en-MY", {
    notation: value >= 10000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(value);

/** Short date for trend axis labels: "12 Jun". */
export const formatShortDate = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-MY", { day: "numeric", month: "short" }).format(d);
};
