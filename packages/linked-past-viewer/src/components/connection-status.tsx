export function ConnectionStatus({ connected }: { connected: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-xs">
      <span
        className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
      />
      {connected ? "connected" : "disconnected"}
    </span>
  );
}
