import { createFileRoute } from "@tanstack/react-router";
import { NetworkGraph } from "#/components/network-graph";

export const Route = createFileRoute("/network/")({
  component: NetworkPage,
  head: () => ({
    meta: [
      { title: "Relationship Network — Liber Amicorum" },
      {
        name: "description",
        content: "Interactive network graph of relationships between Roman Republican figures.",
      },
    ],
  }),
});

function NetworkPage() {
  return (
    <div className="flex h-full flex-col px-6 py-4">
      <div className="mb-3 shrink-0">
        <h1 className="font-heading text-3xl font-bold">Relationship Network</h1>
        <p className="mt-1 text-ink-muted">
          Interactive graph of family, marriage, and political relationships. Use the filters to
          narrow down to an era or gens. Drag nodes to rearrange. Click to view a person's page.
        </p>
      </div>
      <div className="min-h-0 flex-1">
        <NetworkGraph />
      </div>
    </div>
  );
}
