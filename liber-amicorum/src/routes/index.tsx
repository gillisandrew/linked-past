import { Link, createFileRoute } from "@tanstack/react-router";
import { BookOpen, Users, Landmark, BookMarked } from "lucide-react";
import { getPersonsIndex, getOfficesIndex, getSourcesIndex } from "#/lib/data";

export const Route = createFileRoute("/")({
  loader: () => {
    const personsCount = getPersonsIndex().length;
    const officesCount = getOfficesIndex().length;
    const sourcesCount = getSourcesIndex().length;
    return { personsCount, officesCount, sourcesCount };
  },
  component: HomePage,
});

function HomePage() {
  const { personsCount, officesCount, sourcesCount } = Route.useLoaderData();

  const cards = [
    {
      title: "Explore",
      description:
        "Search the prosopographical database with full-text queries across persons, offices, and relationships.",
      href: "/explore",
      icon: BookOpen,
      stat: null,
    },
    {
      title: "Persons",
      description:
        "Browse senators, magistrates, and other political figures of the Roman Republic.",
      href: "/persons",
      icon: Users,
      stat: `${personsCount.toLocaleString()} persons`,
    },
    {
      title: "Offices",
      description:
        "Discover the cursus honorum — the sequence of public offices held by Roman politicians.",
      href: "/offices",
      icon: Landmark,
      stat: `${officesCount.toLocaleString()} offices`,
    },
    {
      title: "Sources",
      description: "Primary and secondary sources cited across the prosopographical database.",
      href: "/sources",
      icon: BookMarked,
      stat: `${sourcesCount.toLocaleString()} sources`,
    },
  ] as const;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <section className="mb-10">
        <h1 className="font-serif text-4xl font-bold tracking-tight text-ink">Liber Amicorum</h1>
        <p className="mt-3 max-w-2xl text-lg text-ink/85">
          A friendly book of the Roman Republic. Explore the people, offices, and political networks
          of Rome through the lens of the Digital Prosopography of the Roman Republic.
        </p>
        <div className="mt-4 flex flex-wrap gap-6 text-sm text-ink-muted">
          <span className="font-medium">{personsCount.toLocaleString()} persons</span>
          <span className="font-medium">{officesCount.toLocaleString()} offices</span>
          <span className="font-medium">{sourcesCount.toLocaleString()} sources</span>
        </div>
      </section>

      <section className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Link
            key={card.title}
            to={card.href}
            className="group rounded-lg border border-ink/10 bg-white/50 p-6 transition-all hover:border-link/30 hover:shadow-md"
          >
            <card.icon className="mb-4 h-8 w-8 text-link" />
            <h2 className="font-serif text-xl font-semibold text-ink">{card.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink/60">{card.description}</p>
            {card.stat && <p className="mt-3 text-xs font-medium text-ink-muted">{card.stat}</p>}
          </Link>
        ))}
      </section>
    </div>
  );
}
