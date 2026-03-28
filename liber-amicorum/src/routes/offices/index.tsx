import { createFileRoute, Link } from "@tanstack/react-router";
import { getAllOffices } from "#/lib/data";

export const Route = createFileRoute("/offices/")({
  loader: () => getAllOffices(),
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
  const offices = Route.useLoaderData();

  // Group offices by parent (top-level offices have parentId === null)
  const topLevel = offices.filter((o) => !o.parentId);
  const byParent = new Map<string, typeof offices>();
  for (const o of offices) {
    if (o.parentId) {
      const group = byParent.get(o.parentId) ?? [];
      group.push(o);
      byParent.set(o.parentId, group);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10 space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-bold">Offices</h1>
        <p className="mt-1 text-ink-muted">{offices.length} offices, grouped by hierarchy.</p>
      </div>
      <div className="space-y-4">
        {topLevel.map((office) => (
          <div key={office.id}>
            <div className="flex items-baseline gap-2">
              <Link
                to="/offices/$officeId"
                params={{ officeId: office.id }}
                className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
              >
                {office.name}
              </Link>
              {office.abbreviation && (
                <span className="text-xs text-ink-muted">({office.abbreviation})</span>
              )}
              <span className="text-xs text-ink-muted">
                &mdash; {office.holders.length} holders
              </span>
            </div>
            {(byParent.get(office.id) ?? []).length > 0 && (
              <div className="ml-6 mt-1 space-y-1">
                {(byParent.get(office.id) ?? []).map((child) => (
                  <div key={child.id} className="flex items-baseline gap-2">
                    <Link
                      to="/offices/$officeId"
                      params={{ officeId: child.id }}
                      className="text-sm text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
                    >
                      {child.name}
                    </Link>
                    {child.abbreviation && (
                      <span className="text-xs text-ink-muted">({child.abbreviation})</span>
                    )}
                    <span className="text-xs text-ink-muted">
                      &mdash; {child.holders.length} holders
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
