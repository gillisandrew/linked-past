import { Link } from "@tanstack/react-router";
import { formatYear } from "#/lib/format";
import type { PostAssertion } from "#/lib/types";
import { Popover, PopoverTrigger, PopoverContent } from "#/components/ui/popover";

const SEGMENT_COLORS = [
  "oklch(0.55 0.10 250)", // deep blue
  "oklch(0.55 0.10 150)", // sage green
  "oklch(0.55 0.08 30)", // terracotta
  "oklch(0.55 0.10 290)", // plum
  "oklch(0.55 0.08 80)", // ochre
  "oklch(0.55 0.10 200)", // teal
  "oklch(0.55 0.08 350)", // rose
  "oklch(0.55 0.10 120)", // olive
];

const HATCH_OVERLAY =
  "repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(255,255,255,0.3) 3px, rgba(255,255,255,0.3) 6px)";

interface CareerTimelineProps {
  eraFrom: number | null;
  eraTo: number | null;
  postAssertions: PostAssertion[];
}

/** Assign each post assertion to a row so overlapping segments stack vertically. */
function assignRows(
  segments: {
    start: number;
    end: number;
    assertion: PostAssertion;
    colorIndex: number;
  }[],
): { row: number; start: number; end: number; assertion: PostAssertion; colorIndex: number }[] {
  const rows: { end: number }[] = [];
  return segments.map((seg) => {
    let row = rows.findIndex((r) => r.end <= seg.start);
    if (row === -1) {
      row = rows.length;
      rows.push({ end: seg.end });
    } else {
      rows[row].end = seg.end;
    }
    return { ...seg, row };
  });
}

export function CareerTimeline({ eraFrom, eraTo, postAssertions }: CareerTimelineProps) {
  if (eraFrom == null || eraTo == null) return null;
  if (postAssertions.length === 0) return null;

  // Ensure a non-zero range
  const rangeStart = eraFrom;
  const rangeEnd = eraTo === eraFrom ? eraTo + 1 : eraTo;
  const span = rangeEnd - rangeStart;

  // Build a color map: one color per unique office
  const officeIds = [...new Set(postAssertions.map((pa) => pa.officeId))];
  const colorMap = new Map(officeIds.map((id, i) => [id, i % SEGMENT_COLORS.length]));

  // Build positioned segments
  const positioned = postAssertions
    .filter((pa) => pa.dateStart != null || pa.dateEnd != null)
    .map((pa) => {
      const start = pa.dateStart ?? pa.dateEnd!;
      const end = pa.dateEnd ?? pa.dateStart!;
      return {
        start: Math.max(start, rangeStart),
        end: Math.min(end === start ? start + 1 : end, rangeEnd),
        assertion: pa,
        colorIndex: colorMap.get(pa.officeId) ?? 0,
      };
    })
    .sort((a, b) => a.start - b.start || a.end - b.end);

  const rowSegments = assignRows(positioned);
  const maxRow = rowSegments.reduce((m, s) => Math.max(m, s.row), 0);
  const ROW_HEIGHT = 18;
  const AXIS_HEIGHT = 20;
  const GAP = 2;
  const totalBarHeight = (maxRow + 1) * (ROW_HEIGHT + GAP);

  // Tick marks
  const ticks: number[] = [rangeStart];
  const step = span <= 20 ? 5 : span <= 60 ? 10 : span <= 150 ? 25 : 50;
  const firstTick = Math.ceil(rangeStart / step) * step;
  for (let t = firstTick; t < rangeEnd; t += step) {
    if (t !== rangeStart) ticks.push(t);
  }
  if (ticks[ticks.length - 1] !== rangeEnd) ticks.push(rangeEnd);

  const pct = (year: number) => ((year - rangeStart) / span) * 100;

  return (
    <div className="w-full">
      {/* Segment area */}
      <div className="relative" style={{ height: totalBarHeight }}>
        {/* Era line */}
        <div
          className="absolute left-0 right-0 bg-ink/20"
          style={{ top: totalBarHeight / 2 - 0.5, height: 1 }}
        />
        {/* Segments */}
        {rowSegments.map((seg, i) => {
          const left = pct(seg.start);
          const width = Math.max(pct(seg.end) - left, 0.5);
          const top = seg.row * (ROW_HEIGHT + GAP);
          const pa = seg.assertion;
          const color = SEGMENT_COLORS[seg.colorIndex];
          const isUncertainAssertion = pa.uncertain;
          const hasUncertainDates = pa.dateStartUncertain || pa.dateEndUncertain;

          return (
            <Popover key={i}>
              <PopoverTrigger
                openOnHover
                delay={150}
                closeDelay={200}
                render={<Link to="/offices/$officeId" params={{ officeId: pa.officeId }} />}
                className="absolute block rounded-sm hover:brightness-110 transition-[filter]"
                style={{
                  left: `${left}%`,
                  width: `${width}%`,
                  top,
                  height: ROW_HEIGHT,
                  minWidth: 4,
                }}
              >
                {/* Base color */}
                <div
                  className="absolute inset-0 rounded-sm"
                  style={{
                    backgroundColor: color,
                    opacity: isUncertainAssertion ? 0.5 : 1,
                  }}
                />
                {/* Hatch overlay for uncertain dates or uncertain assertion */}
                {(hasUncertainDates || isUncertainAssertion) && (
                  <div
                    className="absolute inset-0 rounded-sm"
                    style={{ background: HATCH_OVERLAY }}
                  />
                )}
                {/* Fuzzy gradient at uncertain start */}
                {pa.dateStartUncertain && (
                  <div
                    className="absolute top-0 bottom-0 left-0 w-2 rounded-l-sm"
                    style={{
                      background: `linear-gradient(to right, transparent, ${color})`,
                    }}
                  />
                )}
                {/* Fuzzy gradient at uncertain end */}
                {pa.dateEndUncertain && (
                  <div
                    className="absolute top-0 bottom-0 right-0 w-2 rounded-r-sm"
                    style={{
                      background: `linear-gradient(to left, transparent, ${color})`,
                    }}
                  />
                )}
              </PopoverTrigger>
              <PopoverContent className="w-fit max-w-xs p-2" align="start" side="top">
                <div className="space-y-1">
                  <p className="text-sm font-medium">{pa.office}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatYear(pa.dateStart)} – {formatYear(pa.dateEnd)}
                  </p>
                  {pa.uncertain && <p className="text-xs text-uncertain italic">Uncertain</p>}
                  {pa.province && (
                    <p className="text-xs text-muted-foreground">Province: {pa.province}</p>
                  )}
                  {pa.sources.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Sources: {pa.sources.map((s) => s.name).join(", ")}
                    </p>
                  )}
                </div>
              </PopoverContent>
            </Popover>
          );
        })}
      </div>
      {/* Axis */}
      <div className="relative" style={{ height: AXIS_HEIGHT }}>
        {ticks.map((t) => (
          <span
            key={t}
            className="absolute text-[10px] text-ink-muted -translate-x-1/2"
            style={{ left: `${pct(t)}%` }}
          >
            {formatYear(t)}
          </span>
        ))}
      </div>
    </div>
  );
}
