import { createFileRoute, Link } from "@tanstack/react-router"

export const Route = createFileRoute("/404")({
  component: NotFoundPage,
})

function NotFoundPage() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center space-y-4">
      <h1 className="font-heading text-4xl font-bold">Not Found</h1>
      <p className="text-ink-muted">
        The page you are looking for does not exist.
      </p>
      <Link to="/" className="text-link hover:text-link-light underline">
        Return home
      </Link>
    </div>
  )
}
