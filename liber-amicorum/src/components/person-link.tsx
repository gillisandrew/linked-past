import { Link } from "@tanstack/react-router";
import { formatEra } from "#/lib/format";

interface PersonLinkProps {
  id: string;
  name: string;
  eraFrom?: number | null;
  eraTo?: number | null;
  showEra?: boolean;
}

export function PersonLink({ id, name, eraFrom, eraTo, showEra = false }: PersonLinkProps) {
  return (
    <Link
      to="/persons/$personId"
      params={{ personId: id }}
      className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
    >
      {name}
      {showEra && (eraFrom != null || eraTo != null) && (
        <span className="ml-1 text-xs text-ink-muted">
          ({formatEra(eraFrom ?? null, eraTo ?? null)})
        </span>
      )}
    </Link>
  );
}
