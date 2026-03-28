import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { getOfficesIndex } from "#/lib/data";
import type { OfficeTreeNode } from "#/lib/types";
import { OfficesListingTable } from "#/components/offices-listing-table";

function sumHolderCounts(node: OfficeTreeNode): number {
  let total = node.holderCount;
  for (const child of node.subOffices) {
    total += sumHolderCounts(child);
  }
  node.holderCount = total;
  return total;
}

export const Route = createFileRoute("/offices/")({
  loader: () => {
    const flat = getOfficesIndex();
    const map = new Map<string, OfficeTreeNode>(
      flat.map((o) => [o.id, { ...o, subOffices: [] as OfficeTreeNode[] }]),
    );
    const roots: OfficeTreeNode[] = [];
    for (const node of map.values()) {
      if (node.parentId && map.has(node.parentId)) {
        map.get(node.parentId)!.subOffices.push(node);
      } else {
        roots.push(node);
      }
    }
    // Recursively aggregate holder counts from children into parents
    for (const root of roots) {
      sumHolderCounts(root);
    }
    return { roots, totalCount: flat.length };
  },
  head: () => ({
    meta: [
      { title: "Offices — Liber Amicorum" },
      {
        name: "description",
        content:
          "Browse political and religious offices of the Roman Republic, grouped by hierarchy.",
      },
    ],
  }),
  component: OfficesIndex,
});

const SEGMENT_COLORS = [
  "oklch(0.55 0.10 250)",
  "oklch(0.55 0.10 150)",
  "oklch(0.55 0.08 30)",
  "oklch(0.55 0.10 290)",
  "oklch(0.55 0.08 80)",
  "oklch(0.55 0.10 200)",
  "oklch(0.55 0.08 350)",
  "oklch(0.55 0.10 120)",
];

function OfficesIndex() {
  const { roots, totalCount } = Route.useLoaderData();
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const segments = roots
    .filter((r) => r.holderCount > 0)
    .sort((a, b) => b.holderCount - a.holderCount);
  const total = segments.reduce((sum, s) => sum + s.holderCount, 0);

  return (
    <div className="mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-bold">Offices</h1>
        <p className="mt-1 text-ink-muted">{totalCount} offices, grouped by hierarchy.</p>
      </div>

      {/* Distribution bar */}
      {segments.length > 0 && (
        <div className="flex h-9 w-full overflow-hidden rounded-lg">
          {segments.map((seg, i) => {
            const natural = (seg.holderCount / total) * 100;
            const isHovered = hoveredId === seg.id;
            const minVisible = 8;
            const displayWidth = isHovered && natural < minVisible ? minVisible : natural;
            const color = SEGMENT_COLORS[i % SEGMENT_COLORS.length];

            return (
              <button
                key={seg.id}
                onClick={() => {
                  const el = document.getElementById(`office-${seg.id}`);
                  el?.scrollIntoView({ behavior: "smooth", block: "center" });
                }}
                onMouseEnter={() => setHoveredId(seg.id)}
                onMouseLeave={() => setHoveredId(null)}
                className="relative flex items-center justify-center overflow-hidden border-r border-white/30 last:border-r-0 transition-all duration-200 ease-out cursor-pointer"
                style={{
                  flex: `${displayWidth} 0 0%`,
                  backgroundColor: color,
                }}
                title={`${seg.name}: ${seg.holderCount} holders`}
              >
                <span
                  className={`truncate px-2 text-xs font-medium text-white transition-opacity duration-150 ${
                    natural >= minVisible || isHovered ? "opacity-100" : "opacity-0"
                  }`}
                >
                  {seg.name}
                  <span className="ml-1 opacity-70">({seg.holderCount})</span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      <OfficesListingTable data={roots} />
    </div>
  );
}
