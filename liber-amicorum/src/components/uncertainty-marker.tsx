import { Popover as PopoverPrimitive } from "@base-ui/react/popover";

interface UncertaintyMarkerProps {
  uncertain: boolean;
  children: React.ReactNode;
  /** Brief source label */
  source?: string;
  /** Detailed scholarly notes shown in popover on hover */
  notes?: string[];
}

export function UncertaintyMarker({ uncertain, children, source, notes }: UncertaintyMarkerProps) {
  if (!uncertain) return <>{children}</>;

  const hasNotes = notes && notes.length > 0;

  const styledText = (
    <span className="border-b border-dotted border-uncertain italic">{children}</span>
  );

  if (!hasNotes && !source) {
    return (
      <span className="inline-flex items-baseline gap-0.5">
        {styledText}
        <span className="text-xs font-medium text-uncertain">?</span>
      </span>
    );
  }

  return (
    <span className="inline-flex items-baseline gap-0.5">
      {styledText}
      <PopoverPrimitive.Root>
        <PopoverPrimitive.Trigger
          openOnHover
          delay={200}
          closeDelay={400}
          render={<span />}
          className="cursor-help text-xs font-medium text-uncertain hover:text-uncertain/80"
        >
          ?
        </PopoverPrimitive.Trigger>
        <PopoverPrimitive.Portal>
          <PopoverPrimitive.Positioner align="start" side="bottom" sideOffset={4}>
            <PopoverPrimitive.Popup className="z-50 max-h-80 w-[28rem] overflow-y-auto rounded-lg bg-popover p-3 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10">
              {hasNotes ? (
                <div className="space-y-2">
                  <p className="font-heading text-sm font-medium">Uncertainty Notes</p>
                  {source && <p className="text-xs text-muted-foreground">Source: {source}</p>}
                  {notes.map((note, i) => (
                    <div key={i} className="border-l-2 border-border pl-2">
                      {note
                        .split(/\r?\n\r?\n/)
                        .filter(Boolean)
                        .map((para, j) => (
                          <p key={j} className="mb-1 text-xs leading-relaxed text-foreground/80">
                            {para}
                          </p>
                        ))}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs">Uncertain — {source}</p>
              )}
            </PopoverPrimitive.Popup>
          </PopoverPrimitive.Positioner>
        </PopoverPrimitive.Portal>
      </PopoverPrimitive.Root>
    </span>
  );
}
