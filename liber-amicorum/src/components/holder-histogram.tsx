import { formatYear } from "#/lib/format";
import type { OfficeHolderWithOffice } from "#/lib/types";

const BAR_COLOR = "oklch(0.55 0.10 250)";

const HATCH_OVERLAY =
  "repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(255,255,255,0.3) 3px, rgba(255,255,255,0.3) 6px)";

interface HolderHistogramProps {
  holders: OfficeHolderWithOffice[];
}

interface DecadeBucket {
  decade: number;
  certain: number;
  uncertain: number;
}

function bucketByDecade(holders: OfficeHolderWithOffice[]): DecadeBucket[] {
  const map = new Map<number, { certain: number; uncertain: number }>();

  for (const h of holders) {
    // Use dateStart as the primary date, fall back to dateEnd
    const year = h.dateStart ?? h.dateEnd;
    if (year == null) continue;
    const decade = Math.floor(year / 10) * 10;
    const entry = map.get(decade) ?? { certain: 0, uncertain: 0 };
    if (h.uncertain) {
      entry.uncertain++;
    } else {
      entry.certain++;
    }
    map.set(decade, entry);
  }

  if (map.size === 0) return [];

  // Fill in empty decades so the histogram is continuous
  const decades = [...map.keys()].sort((a, b) => a - b);
  const min = decades[0];
  const max = decades[decades.length - 1];
  const result: DecadeBucket[] = [];
  for (let d = min; d <= max; d += 10) {
    const entry = map.get(d);
    result.push({
      decade: d,
      certain: entry?.certain ?? 0,
      uncertain: entry?.uncertain ?? 0,
    });
  }
  return result;
}

export function HolderHistogram({ holders }: HolderHistogramProps) {
  const buckets = bucketByDecade(holders);
  if (buckets.length === 0) return null;

  const maxCount = Math.max(...buckets.map((b) => b.certain + b.uncertain));
  if (maxCount === 0) return null;

  // Determine label interval: show decade labels every 50 or 100 years
  const totalSpan = buckets[buckets.length - 1].decade - buckets[0].decade;
  const labelStep = totalSpan <= 200 ? 50 : 100;

  return (
    <div className="w-full">
      {/* Bars */}
      <div className="flex items-end gap-px" style={{ height: 100 }}>
        {buckets.map((b) => {
          const total = b.certain + b.uncertain;
          const totalHeight = (total / maxCount) * 100;
          const certainHeight = (b.certain / maxCount) * 100;
          const uncertainHeight = (b.uncertain / maxCount) * 100;
          const tooltip =
            `${total} holder${total !== 1 ? "s" : ""}` +
            (b.uncertain > 0 ? ` (${b.uncertain} uncertain)` : "") +
            ` in ${formatYear(b.decade)}s`;

          return (
            <div
              key={b.decade}
              className="flex-1 flex flex-col justify-end min-w-0"
              style={{ height: "100%" }}
              title={tooltip}
            >
              {/* Uncertain portion (top, hatched) */}
              {b.uncertain > 0 && (
                <div
                  className="w-full relative"
                  style={{ height: `${(uncertainHeight / totalHeight) * 100}%` }}
                >
                  <div
                    className="absolute inset-0"
                    style={{ backgroundColor: BAR_COLOR, opacity: 0.5 }}
                  />
                  <div className="absolute inset-0" style={{ background: HATCH_OVERLAY }} />
                </div>
              )}
              {/* Certain portion (bottom, solid) */}
              {b.certain > 0 && (
                <div
                  className="w-full"
                  style={{
                    height: `${(certainHeight / totalHeight) * 100}%`,
                    backgroundColor: BAR_COLOR,
                  }}
                />
              )}
              {/* Empty spacer to push bars to bottom */}
              {total === 0 && <div className="w-full" />}
            </div>
          );
        })}
      </div>
      {/* Axis labels */}
      <div className="relative h-5 mt-1">
        {buckets.map((b, i) => {
          if (b.decade % labelStep !== 0) return null;
          const left = (i / buckets.length) * 100;
          return (
            <span
              key={b.decade}
              className="absolute text-[10px] text-ink-muted -translate-x-1/2"
              style={{ left: `${left}%` }}
            >
              {formatYear(b.decade)}
            </span>
          );
        })}
      </div>
    </div>
  );
}
