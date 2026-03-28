import { formatYear } from "#/lib/format";
import type { OfficeHolderWithOffice } from "#/lib/types";

const BAR_COLOR = "oklch(0.55 0.10 250)";

const HATCH_OVERLAY =
  "repeating-linear-gradient(45deg, transparent, transparent 2px, rgba(255,255,255,0.4) 2px, rgba(255,255,255,0.4) 4px)";

/** Fixed range: 509 BC (year -509) to 27 BC (year -27) */
const RANGE_START = -509;
const RANGE_END = -27;

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

  // Fixed range from 509 BC to 27 BC, bucketed by decade
  const startDecade = Math.floor(RANGE_START / 10) * 10; // -510
  const endDecade = Math.floor(RANGE_END / 10) * 10; // -30
  const result: DecadeBucket[] = [];
  for (let d = startDecade; d <= endDecade; d += 10) {
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

  const maxCount = Math.max(...buckets.map((b) => b.certain + b.uncertain));
  if (maxCount === 0) return null;

  // Show decade labels every 100 years across the fixed range
  const labelStep = 100;

  return (
    <div className="w-full">
      {/* Bars */}
      <div className="flex items-end gap-px" style={{ height: 100 }}>
        {buckets.map((b) => {
          const total = b.certain + b.uncertain;
          const totalPct = (total / maxCount) * 100;
          const certainPct = total > 0 ? (b.certain / total) * 100 : 0;
          const uncertainPct = total > 0 ? (b.uncertain / total) * 100 : 0;
          const tooltip =
            total > 0
              ? `${total} holder${total !== 1 ? "s" : ""}` +
                (b.uncertain > 0 ? ` (${b.uncertain} uncertain)` : "") +
                ` in ${formatYear(b.decade)}s`
              : `${formatYear(b.decade)}s`;

          return (
            <div
              key={b.decade}
              className="flex-1 flex flex-col justify-end min-w-0"
              style={{ height: "100%" }}
              title={tooltip}
            >
              {total > 0 && (
                <div className="w-full flex flex-col" style={{ height: `${totalPct}%` }}>
                  {/* Uncertain portion (top, hatched) */}
                  {b.uncertain > 0 && (
                    <div className="w-full relative" style={{ height: `${uncertainPct}%` }}>
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
                      className="w-full flex-1"
                      style={{
                        height: `${certainPct}%`,
                        backgroundColor: BAR_COLOR,
                      }}
                    />
                  )}
                </div>
              )}
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
