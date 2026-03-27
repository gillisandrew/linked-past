import { Link } from "@tanstack/react-router";

interface OfficeLinkProps {
  id: string;
  name: string;
  abbreviation?: string | null;
}

export function OfficeLink({ id, name, abbreviation }: OfficeLinkProps) {
  return (
    <Link
      to="/offices/$officeId"
      params={{ officeId: id }}
      className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
    >
      {name}
      {abbreviation && <span className="ml-1 text-xs text-ink-muted">({abbreviation})</span>}
    </Link>
  );
}
