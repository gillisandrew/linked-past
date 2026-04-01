import { isEntityUri } from "../lib/uri";
import { EntityUri } from "./entity-uri";

/**
 * Render a property value — entity URIs get popover + clickable link,
 * plain text renders as-is. showBadge controls inline dataset badge.
 */
export function PropertyValue({
  value,
  className = "",
  showBadge = false,
}: {
  value: string;
  className?: string;
  showBadge?: boolean;
}) {
  if (isEntityUri(value)) {
    return <EntityUri uri={value} display={value} showBadge={showBadge} />;
  }
  return <span className={className}>{value}</span>;
}
