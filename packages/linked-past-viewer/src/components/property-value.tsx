import { isEntityUri } from "../lib/uri";
import { EntityUri } from "./entity-uri";

/**
 * Render a property value — entity URIs get a dataset-colored pill with popover,
 * plain text renders as-is.
 */
export function PropertyValue({
  value,
  className = "",
}: {
  value: string;
  className?: string;
}) {
  if (isEntityUri(value)) {
    return <EntityUri uri={value} display={value} />;
  }
  return <span className={className}>{value}</span>;
}
