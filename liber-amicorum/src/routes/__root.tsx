import { HeadContent, Link, Outlet, Scripts, createRootRoute } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { Agentation } from "agentation";
import appCss from "#/app.css?url";
import { SearchCommand } from "#/components/search-command";

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Liber Amicorum - DPRR Prosopography" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      {
        rel: "preconnect",
        href: "https://fonts.googleapis.com",
      },
      {
        rel: "preconnect",
        href: "https://fonts.gstatic.com",
        crossOrigin: "anonymous",
      },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&display=swap",
      },
    ],
  }),
  shellComponent: RootDocument,
  component: RootLayout,
});

function RootDocument({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body className="min-h-screen bg-parchment font-sans text-ink antialiased">
        {children}
        {process.env.NODE_ENV === "development" && <Agentation endpoint="http://localhost:7373" />}
        <Scripts />
      </body>
    </html>
  );
}

function RootLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b-2 border-ink/10 bg-parchment/80 backdrop-blur-sm">
        <nav className="mx-auto flex items-center justify-between px-6 py-4">
          <Link to="/" className="font-serif text-xl font-bold text-ink">
            Liber Amicorum
          </Link>
          <SearchCommand />
          <ul className="flex items-center gap-6 text-sm font-medium">
            <li>
              <Link to="/" className="font-medium text-ink/70 transition-colors hover:text-ink">
                Home
              </Link>
            </li>
            <li>
              <Link
                to="/persons"
                className="font-medium text-ink/70 transition-colors hover:text-ink"
              >
                Persons
              </Link>
            </li>
            <li>
              <Link
                to="/offices"
                className="font-medium text-ink/70 transition-colors hover:text-ink"
              >
                Offices
              </Link>
            </li>
            <li>
              <Link
                to="/sources"
                className="font-medium text-ink/70 transition-colors hover:text-ink"
              >
                Sources
              </Link>
            </li>
            <li>
              <Link
                to="/explore"
                className="font-medium text-ink/70 transition-colors hover:text-ink"
              >
                Explore
              </Link>
            </li>
          </ul>
        </nav>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-ink/10 py-8 text-sm text-ink/50">
        <div className="mx-auto flex flex-col items-center gap-4 px-6 sm:flex-row sm:justify-between">
          <div className="text-center sm:text-left">
            <p className="font-medium text-ink/70">Liber Amicorum</p>
            <p className="mt-1">A companion to the Digital Prosopography of the Roman Republic</p>
          </div>
          <div className="text-center sm:text-right">
            <p>
              Data from the{" "}
              <a
                href="https://romanrepublic.ac.uk/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
              >
                DPRR Project
              </a>
            </p>
            <p className="mt-1">Licensed under Creative Commons</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
