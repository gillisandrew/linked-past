import { createFileRoute, notFound } from "@tanstack/react-router";
import { getPersonById } from "#/lib/data";
import { formatEra, formatYear } from "#/lib/format";
import { Badge } from "#/components/ui/badge";
import { UncertaintyMarker } from "#/components/uncertainty-marker";
import { SourceBadge } from "#/components/source-badge";
import { PostAssertionsTable } from "#/components/post-assertions-table";
import { StatusAssertionsTable } from "#/components/status-assertions-table";
import { RelationshipsTable } from "#/components/relationships-table";

export const Route = createFileRoute("/persons/$personId")({
  loader: async ({ params }) => {
    const person = await getPersonById(params.personId);
    if (!person) throw notFound();
    return person;
  },
  component: PersonPage,
  head: ({ loaderData }) => ({
    meta: [
      { title: `${loaderData?.name ?? "Person"} \u2014 Liber Amicorum` },
      {
        name: "description",
        content: loaderData
          ? `${loaderData.name}, ${formatEra(loaderData.eraFrom, loaderData.eraTo)}. ${loaderData.highestOffice ?? ""}`
          : "",
      },
    ],
  }),
});

function PersonPage() {
  const person = Route.useLoaderData();

  return (
    <div className="mx-auto px-6 py-10 space-y-8">
      {/* Header: two-column layout with infobox */}
      <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        {/* Left column: name, era, badges */}
        <div className="space-y-2 flex-1 min-w-0">
          <h1 className="font-heading text-3xl font-bold">
            <UncertaintyMarker uncertain={person.praenomenUncertain}>
              {person.praenomen}
            </UncertaintyMarker>{" "}
            <UncertaintyMarker uncertain={person.nomenUncertain}>{person.nomen}</UncertaintyMarker>{" "}
            {person.filiation && (
              <>
                <UncertaintyMarker uncertain={person.filiationUncertain}>
                  <span className="text-2xl font-normal text-ink-muted">{person.filiation}</span>
                </UncertaintyMarker>{" "}
              </>
            )}
            <UncertaintyMarker uncertain={person.cognomenUncertain}>
              {person.cognomen}
            </UncertaintyMarker>
          </h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
            <span>{formatEra(person.eraFrom, person.eraTo)}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {person.patrician && (
              <UncertaintyMarker uncertain={person.patricianUncertain}>
                <Badge variant="outline">Patrician</Badge>
              </UncertaintyMarker>
            )}
            {person.nobilis && <Badge variant="outline">Nobilis</Badge>}
            {person.novus && <Badge variant="outline">Novus Homo</Badge>}
          </div>
        </div>

        {/* Right column: infobox */}
        <div className="border border-ink/10 rounded-lg p-4 bg-white/30 md:w-72 shrink-0">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-2">
              <dt className="text-ink-muted">DPRR ID</dt>
              <dd className="font-medium text-right">{person.id}</dd>
            </div>
            {person.reNumber && (
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">RE Number</dt>
                <dd className="font-medium text-right">{person.reNumber}</dd>
              </div>
            )}
            {person.sex && (
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">Sex</dt>
                <dd className="font-medium text-right">{person.sex}</dd>
              </div>
            )}
            {person.origin && (
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">Origin</dt>
                <dd className="font-medium text-right">{person.origin}</dd>
              </div>
            )}
            {(person.eraFrom != null || person.eraTo != null) && (
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">Era</dt>
                <dd className="font-medium text-right">
                  {formatEra(person.eraFrom, person.eraTo)}
                </dd>
              </div>
            )}
            {person.highestOffice && (
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">Highest Office</dt>
                <dd className="font-medium text-right">{person.highestOffice}</dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {/* Post Assertions */}
      {person.postAssertions.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Offices Held</h2>
          <PostAssertionsTable data={person.postAssertions} />
        </section>
      )}

      {/* Status Assertions */}
      {person.statusAssertions.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Status</h2>
          <StatusAssertionsTable data={person.statusAssertions} />
        </section>
      )}

      {/* Date Information */}
      {person.dateInformation.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Dates</h2>
          <div className="space-y-1">
            {person.dateInformation.map((di, i) => (
              <div key={i} className="flex items-baseline gap-2 text-sm">
                <span className="font-medium capitalize">{di.type}:</span>
                <UncertaintyMarker uncertain={di.uncertain}>
                  {formatYear(di.value) ?? "unknown"}
                </UncertaintyMarker>
                {di.interval && di.interval !== "S" && (
                  <span className="text-xs text-ink-muted">
                    ({di.interval === "B" ? "before" : "after"})
                  </span>
                )}
                {di.source && <SourceBadge name={di.source.name} id={di.source.id} />}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Relationships */}
      {person.relationships.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Relationships</h2>
          <RelationshipsTable data={person.relationships} />
        </section>
      )}

      {/* Tribe Assertions */}
      {person.tribeAssertions.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Tribe</h2>
          <div className="space-y-1">
            {person.tribeAssertions.map((ta, i) => (
              <div key={i} className="flex items-baseline gap-2 text-sm">
                <UncertaintyMarker uncertain={ta.uncertain}>{ta.tribe}</UncertaintyMarker>
                {ta.source && <SourceBadge name={ta.source.name} id={ta.source.id} />}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Notes */}
      {person.notes.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Notes</h2>
          {person.notes.map((note, i) => (
            <p key={i} className="text-sm text-ink-muted">
              {note}
            </p>
          ))}
        </section>
      )}
    </div>
  );
}
