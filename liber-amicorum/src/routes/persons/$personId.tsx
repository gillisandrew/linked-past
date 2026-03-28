import { createFileRoute, notFound } from "@tanstack/react-router";
import { getPersonById } from "#/lib/data";
import { formatEra, formatYear } from "#/lib/format";
import { Badge } from "#/components/ui/badge";
import { UncertaintyMarker } from "#/components/uncertainty-marker";
import { PersonLink } from "#/components/person-link";
import { SourceBadge } from "#/components/source-badge";
import { PostAssertionsTable } from "#/components/post-assertions-table";
import { StatusAssertionsTable } from "#/components/status-assertions-table";

export const Route = createFileRoute("/persons/$personId")({
  loader: ({ params }) => {
    const person = getPersonById(params.personId);
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
    <div className="mx-auto max-w-5xl px-6 py-10 space-y-8">
      {/* Header */}
      <div className="space-y-2">
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
          {person.sex && <span>&middot; {person.sex}</span>}
          {person.origin && <span>&middot; {person.origin}</span>}
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
        {person.reNumber && <p className="text-xs text-ink-muted">RE: {person.reNumber}</p>}
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
                {di.source && <SourceBadge name={di.source.name} />}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Relationships */}
      {person.relationships.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Relationships</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {person.relationships.map((rel, i) => (
              <div key={i} className="rounded-lg border border-parchment-dark p-3">
                <p className="text-xs uppercase text-ink-muted">{rel.type}</p>
                {rel.relatedPersonId && rel.relatedPersonName ? (
                  <PersonLink id={rel.relatedPersonId} name={rel.relatedPersonName} />
                ) : (
                  <span className="text-sm text-ink-muted">
                    {rel.relatedPersonName ?? "Unknown"}
                  </span>
                )}
              </div>
            ))}
          </div>
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
                {ta.source && <SourceBadge name={ta.source.name} />}
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
