import { createFileRoute } from "@tanstack/react-router";
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

function OfficesIndex() {
  const { roots, totalCount } = Route.useLoaderData();

  return (
    <div className="mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-bold">Offices</h1>
        <p className="mt-1 text-ink-muted">{totalCount} offices, grouped by hierarchy.</p>
      </div>
      <OfficesListingTable data={roots} />
    </div>
  );
}
