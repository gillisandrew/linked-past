import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "#/components/ui/tooltip";

interface UncertaintyMarkerProps {
  uncertain: boolean;
  children: React.ReactNode;
  /** Brief source label shown in tooltip */
  source?: string;
  /** Detailed scholarly notes shown in tooltip on hover */
  notes?: string[];
}

export function UncertaintyMarker({ uncertain, children, source, notes }: UncertaintyMarkerProps) {
  if (!uncertain) return <>{children}</>;

  const hasNotes = notes && notes.length > 0;
  const hasTooltip = hasNotes || source;

  const styledContent = (
    <span className="inline-flex items-baseline gap-0.5">
      <span className="border-b border-dotted border-uncertain italic">{children}</span>
      <span className="text-uncertain text-xs font-medium">?</span>
    </span>
  );

  if (!hasTooltip) return styledContent;

  return (
    <TooltipProvider>
      <Tooltip delayDuration={200}>
        <TooltipTrigger asChild>
          <span className="cursor-help">{styledContent}</span>
        </TooltipTrigger>
        <TooltipContent
          className={hasNotes ? "max-h-64 w-96 overflow-y-auto" : ""}
          align="start"
          side="bottom"
        >
          <div className="space-y-1.5">
            {source && !hasNotes && (
              <p className="text-xs">Uncertain — {source}</p>
            )}
            {hasNotes && (
              <>
                {source && <p className="text-xs text-muted-foreground">Source: {source}</p>}
                {notes.map((note, i) => (
                  <p key={i} className="text-xs leading-relaxed">
                    {note}
                  </p>
                ))}
              </>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
