import { createFileRoute, Link } from "@tanstack/react-router";
import { getPersonsIndex } from "#/lib/data";
import { formatEra } from "#/lib/format";

export const Route = createFileRoute("/persons/")({
  loader: () => getPersonsIndex().sort((a, b) => (a.nomen ?? "").localeCompare(b.nomen ?? "")),
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
    <div className="mx-auto max-w-5xl px-6 py-10 space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-bold">Persons</h1>
        <p className="mt-1 text-ink-muted">{persons.length} individuals, alphabetical by nomen.</p>
      </div>
      <div className="space-y-1">
        {persons.map((p) => (
          <div key={p.id} className="flex items-baseline gap-3 py-1">
            <Link
              to="/persons/$personId"
              params={{ personId: p.id }}
              className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
            >
              {p.name}
            </Link>
            <span className="text-xs text-ink-muted">{formatEra(p.eraFrom, p.eraTo)}</span>
            {p.highestOffice && (
              <span className="text-xs text-ink-muted">&mdash; {p.highestOffice}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
