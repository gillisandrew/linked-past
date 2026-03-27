import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "#/components/ui/tooltip";

interface UncertaintyMarkerProps {
  uncertain: boolean;
  children: React.ReactNode;
  source?: string;
}

export function UncertaintyMarker({ uncertain, children, source }: UncertaintyMarkerProps) {
  if (!uncertain) return <>{children}</>;

  const content = (
    <span className="border-b border-dotted border-uncertain italic">
      {children}
      <span className="text-uncertain">?</span>
    </span>
  );

  if (!source) return content;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{content}</TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">Uncertain — {source}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
