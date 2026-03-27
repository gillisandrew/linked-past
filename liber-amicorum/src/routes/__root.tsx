import { HeadContent, Outlet, Scripts, createRootRoute } from "@tanstack/react-router";
import type { ReactNode } from "react";
import appCss from "#/app.css?url";

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
        <Scripts />
      </body>
    </html>
  );
}

function RootLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-ink/10 bg-parchment/80 backdrop-blur-sm">
        <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <a href="/" className="font-serif text-xl font-bold text-ink">
            Liber Amicorum
          </a>
          <ul className="flex items-center gap-6 text-sm font-medium">
            <li>
              <a href="/" className="text-ink/70 transition-colors hover:text-ink">
                Home
              </a>
            </li>
            <li>
              <a href="/persons" className="text-ink/70 transition-colors hover:text-ink">
                Persons
              </a>
            </li>
            <li>
              <a href="/offices" className="text-ink/70 transition-colors hover:text-ink">
                Offices
              </a>
            </li>
          </ul>
        </nav>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-ink/10 py-8 text-center text-sm text-ink/50">
        <p>Liber Amicorum &mdash; A companion to the Digital Prosopography of the Roman Republic</p>
      </footer>
    </div>
  );
}
