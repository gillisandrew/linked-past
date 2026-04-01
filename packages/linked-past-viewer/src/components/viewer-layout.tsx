export function ViewerLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur px-4 h-10 flex items-center text-sm">
        <span className="font-semibold">linked-past viewer</span>
      </header>
      <main className="max-w-4xl mx-auto p-4">
        <p className="text-muted-foreground text-center py-20">
          Waiting for results… Run a query in Claude to see results here.
        </p>
      </main>
    </div>
  );
}
