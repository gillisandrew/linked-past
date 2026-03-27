import { Badge } from "#/components/ui/badge";

interface SourceBadgeProps {
  name: string;
}

export function SourceBadge({ name }: SourceBadgeProps) {
  return (
    <Badge variant="secondary" className="text-xs font-normal">
      {name}
    </Badge>
  );
}
