import { useEffect, useRef, useState } from "react";
import { TableRow } from "#/components/ui/table";

interface AnchorRowProps {
  id: string;
  children: React.ReactNode;
}

export function AnchorRow({ id, children }: AnchorRowProps) {
  const ref = useRef<HTMLTableRowElement>(null);
  const [highlighted, setHighlighted] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.location.hash === `#${id}`) {
      ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlighted(true);
      const timer = setTimeout(() => setHighlighted(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [id]);

  return (
    <TableRow
      ref={ref}
      id={id}
      className={highlighted ? "bg-link/10 transition-colors duration-1000" : ""}
    >
      {children}
    </TableRow>
  );
}
