const URI_NAMESPACES: Record<string, string> = {
  "http://romanrepublic.ac.uk/rdf/": "dprr",
  "http://www.romanrepublic.ac.uk/rdf/": "dprr",
  "https://romanrepublic.ac.uk/rdf/": "dprr",
  "https://www.romanrepublic.ac.uk/rdf/": "dprr",
  "https://pleiades.stoa.org/places/": "pleiades",
  "http://pleiades.stoa.org/places/": "pleiades",
  "http://n2t.net/ark:/99152/": "periodo",
  "https://n2t.net/ark:/99152/": "periodo",
  "http://nomisma.org/id/": "nomisma",
  "https://nomisma.org/id/": "nomisma",
  "http://numismatics.org/crro/id/": "crro",
  "https://numismatics.org/crro/id/": "crro",
  "http://numismatics.org/ocre/id/": "ocre",
  "https://numismatics.org/ocre/id/": "ocre",
  "http://edh-www.adw.uni-heidelberg.de/edh/": "edh",
  "https://edh-www.adw.uni-heidelberg.de/edh/": "edh",
  "http://edh.ub.uni-heidelberg.de/edh/": "edh",
  "https://edh.ub.uni-heidelberg.de/edh/": "edh",
};

export function datasetForUri(uri: string): string | null {
  for (const [ns, ds] of Object.entries(URI_NAMESPACES)) {
    if (uri.startsWith(ns)) return ds;
  }
  return null;
}

/**
 * Compress a full URI to prefixed form using known namespace prefixes.
 * Falls back to the last path/fragment segment if no prefix matches.
 *
 * Examples:
 *   http://nomisma.org/id/rome → nm:rome
 *   http://romanrepublic.ac.uk/rdf/entity/Person/1 → entity:Person/1
 *   http://unknown.org/foo → foo
 */
const COMPRESS_PREFIXES: [string, string][] = [
  ["http://romanrepublic.ac.uk/rdf/ontology#", "vocab:"],
  ["http://romanrepublic.ac.uk/rdf/entity/", "entity:"],
  ["http://nomisma.org/ontology#", "nmo:"],
  ["http://nomisma.org/id/", "nm:"],
  ["http://numismatics.org/crro/id/", "crro:"],
  ["http://numismatics.org/ocre/id/", "ocre:"],
  ["https://pleiades.stoa.org/places/", "pleiades:"],
  ["http://n2t.net/ark:/99152/", "periodo:"],
  ["http://edh-www.adw.uni-heidelberg.de/edh/", "edh:"],
  ["https://edh-www.adw.uni-heidelberg.de/edh/", "edh:"],
  ["http://www.w3.org/2004/02/skos/core#", "skos:"],
  ["http://www.w3.org/2000/01/rdf-schema#", "rdfs:"],
  ["http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:"],
  ["http://xmlns.com/foaf/0.1/", "foaf:"],
  ["http://purl.org/dc/terms/", "dcterms:"],
  ["http://www.w3.org/ns/org#", "org:"],
  ["http://lawd.info/ontology/", "lawd:"],
  ["http://www.w3.org/2003/01/geo/wgs84_pos#", "geo:"],
];

export function shortUri(uri: string): string {
  for (const [ns, prefix] of COMPRESS_PREFIXES) {
    if (uri.startsWith(ns)) return prefix + uri.slice(ns.length);
  }
  // Fallback: last path segment or fragment
  return uri.split("/").pop()?.split("#").pop() ?? uri;
}

/**
 * Format a URI as a markdown link: [prefixed](https://full-uri).
 * Converts http:// to https:// for the link target.
 * Returns plain text if the URI can't be resolved to a full URL.
 */
export function markdownLink(uri: string, prefixMap?: Record<string, string>): string {
  const full = expandPrefixedUri(uri, prefixMap ?? {});
  const short = shortUri(full);
  if (full.startsWith("http://") || full.startsWith("https://")) {
    const href = full.replace(/^http:\/\//, "https://");
    return `[${short}](${href})`;
  }
  return `\`${short}\``;
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
