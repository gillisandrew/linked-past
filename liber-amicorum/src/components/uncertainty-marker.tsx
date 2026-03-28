import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "#/components/ui/tooltip";
import { Popover, PopoverContent, PopoverTrigger } from "#/components/ui/popover";

interface UncertaintyMarkerProps {
  uncertain: boolean;
  children: React.ReactNode;
  /** Brief source label shown in tooltip */
  source?: string;
  /** Detailed scholarly notes shown in popover on click */
  notes?: string[];
}

export function UncertaintyMarker({ uncertain, children, source, notes }: UncertaintyMarkerProps) {
  if (!uncertain) return <>{children}</>;

  const hasNotes = notes && notes.length > 0;
  const hasTooltip = !hasNotes && !!source;

  const styledContent = (
    <span className="inline-flex items-baseline gap-0.5">
      <span className="border-b border-dotted border-uncertain italic">{children}</span>
      {!hasNotes && <span className="text-uncertain text-xs font-medium">?</span>}
    </span>
  );

  // Notes present: render Popover (click to open) with a Tooltip hint
  if (hasNotes) {
    return (
      <span className="inline-flex items-baseline gap-0.5">
        <span className="border-b border-dotted border-uncertain italic">{children}</span>
        <Popover>
          <TooltipProvider delay={300}>
            <Tooltip>
              <PopoverTrigger asChild>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="text-uncertain hover:text-uncertain/80 cursor-pointer text-xs font-medium"
                  >
                    ?
                  </button>
                </TooltipTrigger>
              </PopoverTrigger>
              <TooltipContent side="top">
                <p className="text-xs">Click for uncertainty details</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <PopoverContent className="max-h-80 w-[28rem] overflow-y-auto" align="start">
            <div className="space-y-3">
              <p className="text-sm font-medium text-ink">Uncertainty Notes</p>
              {source && <p className="text-xs text-ink-muted">Source: {source}</p>}
              {notes.map((note, i) => (
                <div key={i} className="border-l-2 border-link/20 pl-3">
                  {note
                    .split(/\r?\n\r?\n/)
                    .filter(Boolean)
                    .map((para, j) => (
                      <p key={j} className="mb-1.5 text-xs leading-relaxed text-ink/80">
                        {para}
                      </p>
                    ))}
                </div>
              ))}
            </div>
          </PopoverContent>
        </Popover>
      </span>
    );
  }

  // Source only (no notes): simple tooltip
  if (hasTooltip) {
    return (
      <TooltipProvider>
        <Tooltip delayDuration={200}>
          <TooltipTrigger asChild>
            <span className="cursor-help">{styledContent}</span>
          </TooltipTrigger>
          <TooltipContent align="start" side="bottom">
            <p className="text-xs">Uncertain — {source}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // No tooltip content at all
  return styledContent;
}
