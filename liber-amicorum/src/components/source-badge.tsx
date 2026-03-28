import { Link } from "@tanstack/react-router";
import { Badge } from "#/components/ui/badge";

interface SourceBadgeProps {
  name: string;
  id: string;
}

export function SourceBadge({ name, id }: SourceBadgeProps) {
  return (
    <Link to="/sources/$sourceId" params={{ sourceId: id }}>
      <Badge
        variant="secondary"
        className="text-xs font-normal cursor-pointer hover:bg-secondary/80"
      >
        {name}
      </Badge>
    </Link>
  );
}
