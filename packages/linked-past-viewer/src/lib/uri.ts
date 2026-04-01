const URI_NAMESPACES: Record<string, string> = {
  "http://romanrepublic.ac.uk/rdf/": "dprr",
  "https://pleiades.stoa.org/places/": "pleiades",
  "http://n2t.net/ark:/99152/": "periodo",
  "http://nomisma.org/id/": "nomisma",
  "http://numismatics.org/crro/id/": "crro",
  "http://numismatics.org/ocre/id/": "ocre",
  "http://edh-www.adw.uni-heidelberg.de/edh/": "edh",
  "https://edh-www.adw.uni-heidelberg.de/edh/": "edh",
};

export function datasetForUri(uri: string): string | null {
  for (const [ns, ds] of Object.entries(URI_NAMESPACES)) {
    if (uri.startsWith(ns)) return ds;
  }
  return null;
}

export function shortUri(uri: string): string {
  return uri.split("/").pop()?.split("#").pop() ?? uri;
}

/**
 * Check if a value looks like a prefixed URI (e.g., "entity:Person/123", "vocab:hasName").
 * Must have a prefix part, a colon, and a local part with no spaces.
 * Excludes plain text like "Province: provincia declined".
 */
export function isPrefixedUri(value: string): boolean {
  return /^[a-zA-Z][\w-]*:\S+$/.test(value) && !value.startsWith("http");
}

/**
 * Check if a value is any kind of URI — full or prefixed.
 */
export function isEntityUri(value: string): boolean {
  return value.startsWith("http://") || value.startsWith("https://") || isPrefixedUri(value);
}

/**
 * Expand a prefixed URI to a full URI using a prefix map.
 * Returns the original value if no expansion is possible.
 */
export function expandPrefixedUri(value: string, prefixMap: Record<string, string>): string {
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  const colonIdx = value.indexOf(":");
  if (colonIdx < 1) return value;
  const prefix = value.substring(0, colonIdx);
  const local = value.substring(colonIdx + 1);
  const ns = prefixMap[prefix];
  return ns ? `${ns}${local}` : value;
}
