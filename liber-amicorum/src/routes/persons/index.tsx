import { createFileRoute } from "@tanstack/react-router";
import { getPersonsIndex } from "#/lib/data";
import { PersonsListingTable } from "#/components/persons-listing-table";

export const Route = createFileRoute("/persons/")({
  loader: () => getPersonsIndex(),
  head: () => ({
    meta: [
      { title: "Persons — Liber Amicorum" },
      {
        name: "description",
        content:
          "Browse all individuals from the Digital Prosopography of the Roman Republic, alphabetical by family name.",
      },
    ],
  }),
  component: PersonsIndex,
});

function PersonsIndex() {
  const persons = Route.useLoaderData();

  return (
    <div className="mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-bold">Persons</h1>
        <p className="mt-1 text-ink-muted">{persons.length} individuals, alphabetical by nomen.</p>
      </div>
      <PersonsListingTable data={persons} />
    </div>
  );
}
