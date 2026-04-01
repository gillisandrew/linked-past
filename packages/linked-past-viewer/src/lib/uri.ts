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
