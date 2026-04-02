import { Wifi, WifiOff } from "lucide-react";

export function ConnectionStatus({ connected }: { connected: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs ${
        connected ? "text-green-600 dark:text-green-400" : "text-red-500"
      }`}
    >
      {connected ? (
        <Wifi className="w-3.5 h-3.5" />
      ) : (
        <WifiOff className="w-3.5 h-3.5" />
      )}
      <span>{connected ? "connected" : "disconnected"}</span>
    </span>
  );
}
