/**
 * Format a year value for display. Negative = BC, positive = AD.
 * Returns null if value is null/undefined.
 */
export function formatYear(value: number | null | undefined): string | null {
  if (value == null) return null;
  if (value < 0) return `${Math.abs(value)} BC`;
  return `${value} AD`;
}

/**
 * Format a date range (eraFrom - eraTo).
 */
export function formatEra(from: number | null, to: number | null): string {
  const f = formatYear(from);
  const t = formatYear(to);
  if (f && t && f !== t) return `${f} \u2013 ${t}`;
  if (f) return f;
  if (t) return t;
  return "unknown";
}

/**
 * Format a year with uncertainty marker.
 */
export function formatYearUncertain(value: number | null, uncertain: boolean): string | null {
  const formatted = formatYear(value);
  if (!formatted) return null;
  return uncertain ? `${formatted}?` : formatted;
}

/**
 * Build a stable, URL-friendly anchor ID from a prefix and parts.
 */
export function assertionAnchor(
  prefix: string,
  ...parts: (string | number | null | undefined)[]
): string {
  return [prefix, ...parts.filter((p) => p != null).map((p) => String(p))]
    .join("-")
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-+/g, "-");
}
