import { isEntityUri } from "../lib/uri";
import { EntityUri } from "./entity-uri";

/**
 * Render a property value — entity URIs get popover + clickable link
 * (displaying the full URI as link text), plain text renders as-is.
 */
export function PropertyValue({
  value,
  className = "",
}: {
  value: string;
  className?: string;
}) {
  if (isEntityUri(value)) {
    return <EntityUri uri={value} display={value} showBadge={false} />;
  }
  return <span className={className}>{value}</span>;
}
