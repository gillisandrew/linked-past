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
      className="text-accent hover:text-accent-light underline decoration-accent/30 hover:decoration-accent"
    >
      {name}
      {abbreviation && <span className="ml-1 text-xs text-ink-muted">({abbreviation})</span>}
    </Link>
  );
}
