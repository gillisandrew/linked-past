import type { XrefLink } from "../lib/types";
export function XrefList({ links }: { links: XrefLink[] }) {
  return <pre className="text-xs">{JSON.stringify(links, null, 2)}</pre>;
}
