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
    <div className="px-6 py-4">
      <div className="mb-4">
        <h1 className="font-heading text-3xl font-bold">Relationship Network</h1>
        <p className="mt-1 text-ink-muted">
          Interactive graph of family, marriage, and political relationships. Drag nodes to
          rearrange. Click to view a person's page.
        </p>
      </div>
      <NetworkGraph />
    </div>
  );
}
