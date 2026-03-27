import { Link, createFileRoute } from "@tanstack/react-router";
import { BookOpen, Users, Landmark } from "lucide-react";

export const Route = createFileRoute("/")({
  component: HomePage,
});

const cards = [
  {
    title: "Explore",
    description:
      "Search the prosopographical database with full-text queries across persons, offices, and relationships.",
    href: "/explore",
    icon: BookOpen,
  },
  {
    title: "Persons",
    description: "Browse senators, magistrates, and other political figures of the Roman Republic.",
    href: "/persons",
    icon: Users,
  },
  {
    title: "Offices",
    description:
      "Discover the cursus honorum — the sequence of public offices held by Roman politicians.",
    href: "/offices",
    icon: Landmark,
  },
] as const;

function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-16">
      <section className="mb-16 text-center">
        <h1 className="font-serif text-4xl font-bold tracking-tight text-ink sm:text-5xl">
          Liber Amicorum
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-ink/70">
          A friendly book of the Roman Republic. Explore the people, offices, and political networks
          of Rome through the lens of the Digital Prosopography of the Roman Republic.
        </p>
      </section>

      <section className="grid gap-6 sm:grid-cols-3">
        {cards.map((card) => (
          <Link
            key={card.title}
            to={card.href}
            className="group rounded-lg border border-ink/10 bg-white/50 p-6 transition-all hover:border-link/30 hover:shadow-md"
          >
            <card.icon className="mb-4 h-8 w-8 text-link" />
            <h2 className="font-serif text-xl font-semibold text-ink">{card.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink/60">{card.description}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
