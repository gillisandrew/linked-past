import { createFileRoute } from "@tanstack/react-router";
import { getAllPersons } from "#/lib/data";
import { ExploreTable } from "#/components/explore-table";

export const Route = createFileRoute("/explore/")({
  loader: () => getAllPersons(),
  head: () => ({
    meta: [
      { title: "Explore — Liber Amicorum" },
      {
        name: "description",
        content:
          "Search, sort, and filter the full DPRR dataset of Roman Republican individuals.",
      },
    ],
  }),
  component: ExplorePage,
});

function ExplorePage() {
  const persons = Route.useLoaderData();

  return (
    <div className="mx-auto max-w-5xl px-6 py-10 space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-bold">Explore</h1>
        <p className="mt-1 text-ink-muted">
          Search, sort, and filter the full dataset of {persons.length} individuals.
        </p>
      </div>
      <ExploreTable data={persons} />
    </div>
  );
}
