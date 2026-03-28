import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { ExternalLink } from "lucide-react";

// Muted, scholarly color palette for segments
const SEGMENT_COLORS = [
  "oklch(0.55 0.10 250)", // deep blue
  "oklch(0.55 0.10 150)", // sage green
  "oklch(0.55 0.08 30)",  // terracotta
  "oklch(0.55 0.10 290)", // plum
  "oklch(0.55 0.08 80)",  // ochre
  "oklch(0.55 0.10 200)", // teal
  "oklch(0.55 0.08 350)", // rose
  "oklch(0.55 0.10 120)", // olive
];

interface OfficeSegment {
  id: string;
  name: string;
  count: number;
}

interface OfficeDistributionBarProps {
  segments: OfficeSegment[];
  selectedOffices: Set<string>;
  onToggle: (officeId: string) => void;
}

export function OfficeDistributionBar({
  segments,
  selectedOffices,
  onToggle,
}: OfficeDistributionBarProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const total = segments.reduce((sum, s) => sum + s.count, 0);

  // Compute flex values: base is proportional, but expand hovered small segments
  const MIN_VISIBLE = 8; // minimum percentage width so labels fit

  return (
    <div className="space-y-1.5">
      <div className="flex h-9 w-full overflow-hidden rounded-lg">
        {segments.map((seg, i) => {
          const natural = (seg.count / total) * 100;
          const isHovered = hoveredId === seg.id;
          const isActive = selectedOffices.has(seg.id);
          const color = SEGMENT_COLORS[i % SEGMENT_COLORS.length];

          // When hovered, expand small segments to readable size
          const displayWidth = isHovered && natural < MIN_VISIBLE ? MIN_VISIBLE : natural;

          return (
            <button
              key={seg.id}
              onClick={() => onToggle(seg.id)}
              onMouseEnter={() => setHoveredId(seg.id)}
              onMouseLeave={() => setHoveredId(null)}
              className="relative flex items-center justify-center overflow-hidden border-r border-white/30 last:border-r-0 transition-all duration-200 ease-out cursor-pointer"
              style={{
                flex: `${displayWidth} 0 0%`,
                backgroundColor: color,
                opacity: isActive ? 1 : 0.3,
              }}
              title={`${seg.name}: ${seg.count} holders — click to ${isActive ? "hide" : "show"}`}
            >
              {/* Label — visible when segment is wide enough or hovered */}
              <span
                className={`truncate px-2 text-xs font-medium text-white transition-opacity duration-150 ${
                  natural >= MIN_VISIBLE || isHovered ? "opacity-100" : "opacity-0"
                }`}
              >
                {seg.name}
                <span className="ml-1 opacity-70">({seg.count})</span>
              </span>

              {/* Link icon — appears on hover */}
              {isHovered && (
                <Link
                  to="/offices/$officeId"
                  params={{ officeId: seg.id }}
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-0.5 text-white/60 hover:text-white hover:bg-white/20 transition-colors"
                  title={`Go to ${seg.name}`}
                >
                  <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
