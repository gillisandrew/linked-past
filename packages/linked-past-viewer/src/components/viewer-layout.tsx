import { useViewerSocket } from "../hooks/use-viewer-socket";
import { ConnectionStatus } from "./connection-status";
import { Feed } from "./feed";

export function ViewerLayout() {
  const { messages, isConnected } = useViewerSocket();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur px-4 h-10 flex items-center text-sm">
        <span className="font-semibold">linked-past viewer</span>
        <span className="ml-auto">
          <ConnectionStatus connected={isConnected} />
        </span>
      </header>
      <main className="max-w-4xl mx-auto p-4">
        <Feed messages={messages} />
      </main>
    </div>
  );
}
