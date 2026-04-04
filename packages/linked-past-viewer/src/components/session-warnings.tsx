import { AlertTriangle } from "lucide-react";
import type { ParseError } from "@/lib/parse-session";

export function FormatVersionWarning({
  formatVersion,
  currentVersion,
}: {
  formatVersion: number | null;
  currentVersion: number;
}) {
  if (formatVersion === null || formatVersion <= currentVersion) return null;

  return (
    <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-700 dark:text-amber-400 flex items-center gap-2">
      <AlertTriangle className="h-4 w-4 flex-shrink-0" />
      This session was created with a newer format (v{formatVersion}). Some
      items may not render correctly.
    </div>
  );
}

export function ParseErrorBanner({ errors }: { errors: ParseError[] }) {
  if (errors.length === 0) return null;

  return (
    <div className="border-b border-amber-500/30 bg-amber-500/5 px-4 py-3 space-y-2">
      <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
        {errors.length} line{errors.length !== 1 ? "s" : ""} could not be
        parsed:
      </p>
      {errors.map((err) => (
        <div
          key={err.line}
          className="text-xs font-mono bg-amber-500/10 rounded px-2 py-1.5 border border-amber-500/20"
        >
          <span className="text-amber-600 dark:text-amber-400 font-semibold">
            Line {err.line}:
          </span>{" "}
          <span className="text-muted-foreground">{err.error}</span>
          <div className="mt-1 text-muted-foreground/70 truncate">
            {err.raw}
          </div>
        </div>
      ))}
    </div>
  );
}
