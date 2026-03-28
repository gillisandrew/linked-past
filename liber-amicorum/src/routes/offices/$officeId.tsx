import { createFileRoute, notFound, Link } from "@tanstack/react-router";
import { getOfficeById } from "#/lib/data";
import { OfficeLink } from "#/components/office-link";
import { HoldersTable } from "#/components/holders-table";

export const Route = createFileRoute("/offices/$officeId")({
  loader: async ({ params }) => {
    const office = await getOfficeById(params.officeId);
    if (!office) throw notFound();
    return office;
  },
  component: OfficePage,
  head: ({ loaderData }) => ({
    meta: [
      { title: `${loaderData?.name ?? "Office"} \u2014 Liber Amicorum` },
      {
        name: "description",
        content: loaderData
          ? `${loaderData.name}${loaderData.abbreviation ? ` (${loaderData.abbreviation})` : ""} \u2014 ${loaderData.holders.length} known holders`
          : "",
      },
    ],
  }),
});

function OfficePage() {
  const office = Route.useLoaderData();

  return (
    <div className="mx-auto px-6 py-10 space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="font-heading text-3xl font-bold">{office.name}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          {office.abbreviation && <span>{office.abbreviation}</span>}
          {office.parentName && office.parentId && (
            <>
              <span>&middot;</span>
              <span>
                Parent: <OfficeLink id={office.parentId} name={office.parentName} />
              </span>
            </>
          )}
          <span>&middot; {office.holders.length} known holders</span>
        </div>
      </div>

      {/* Child offices */}
      {office.children.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Sub-offices</h2>
          <div className="flex flex-wrap gap-3">
            {office.children.map((child) => (
              <Link
                key={child.id}
                to="/offices/$officeId"
                params={{ officeId: child.id }}
                className="rounded-lg border border-parchment-dark px-4 py-2 text-sm text-link hover:bg-parchment-dark"
              >
                {child.name}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Holders */}
      {office.holders.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Holders</h2>
          <HoldersTable data={office.holders} />
        </section>
      )}
    </div>
  );
}
