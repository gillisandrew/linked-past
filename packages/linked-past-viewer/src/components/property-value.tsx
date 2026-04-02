import { isEntityUri, isPrefixedUri } from "../lib/uri";
import { EntityUri } from "./entity-uri";

/**
 * Render a property value — entity URIs get a dataset-colored pill with popover,
 * plain text renders as-is. Full URIs get compressed to prefixed form automatically.
 */
export function PropertyValue({
  value,
  className = "",
}: {
  value: string;
  className?: string;
}) {
  if (isEntityUri(value)) {
    // Already-prefixed URIs (e.g., "nm:rome") keep their display.
    // Full URIs omit display so EntityUri uses shortUri() compression.
    const display = isPrefixedUri(value) ? value : undefined;
    return <EntityUri uri={value} display={display} />;
  }
  return <span className={className}>{value}</span>;
}
