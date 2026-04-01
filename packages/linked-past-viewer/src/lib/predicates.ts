/**
 * Human-friendly labels for common RDF predicates.
 * Falls back to camelCase → "Camel Case" conversion.
 */

const PREDICATE_LABELS: Record<string, string> = {
  // DPRR
  hasPersonName: "Name",
  hasDprrID: "DPRR ID",
  hasAssociatedWebpage: "Webpage",
  hasReNumber: "RE Number",
  hasFiliation: "Filiation",
  hasID: "ID",
  hasName: "Name",
  hasHighestOffice: "Highest Office",
  hasNomen: "Nomen",
  hasCognomen: "Cognomen",
  hasPraenomen: "Praenomen",
  hasGender: "Gender",
  hasEraFrom: "Date From",
  hasEraTo: "Date To",
  hasDateBirth: "Born",
  hasDateDeath: "Died",
  hasLifeDates: "Life Dates",
  hasDateNote: "Date Note",
  hasPostAssertionNote: "Office Note",
  hasPostAssertion: "Office",
  hasRelationshipAssertion: "Relationship",
  hasStatusAssertion: "Status",
  hasTribalAssertion: "Tribe",
  hasPersonNote: "Note",
  hasExtraInfo: "Extra Info",
  hasOtherNames: "Other Names",
  hasOrigin: "Origin",
  isSex: "Sex",
  isNobilis: "Nobilis",
  isPatrician: "Patrician",
  isNovus: "Novus Homo",
  isCognomenUncertain: "Cognomen Uncertain",
  isNomenUncertain: "Nomen Uncertain",
  isPraenomenUncertain: "Praenomen Uncertain",
  isFiliationUncertain: "Filiation Uncertain",

  // Common RDF/RDFS/SKOS
  label: "Label",
  prefLabel: "Preferred Label",
  altLabel: "Alt Label",
  comment: "Description",
  description: "Description",
  seeAlso: "See Also",
  isDefinedBy: "Defined By",

  // Dublin Core
  title: "Title",
  creator: "Creator",
  date: "Date",
  subject: "Subject",
  source: "Source",

  // FOAF
  name: "Name",
  homepage: "Homepage",
  depiction: "Image",

  // Nomisma
  hasAuthority: "Authority",
  hasMint: "Mint",
  hasDenomination: "Denomination",
  hasManufacture: "Manufacture",
  hasTypeSeriesItem: "Type Series",
  hasStartDate: "Start Date",
  hasEndDate: "End Date",
  hasObverse: "Obverse",
  hasReverse: "Reverse",

  // EDH
  hasEditionText: "Inscription Text",
  hasFindspot: "Findspot",
  hasMaterial: "Material",
  hasObjectType: "Object Type",
  hasNotBefore: "Not Before",
  hasNotAfter: "Not After",

  // Pleiades
  hasLocation: "Location",
  hasFeatureType: "Feature Type",
  hasConnectionWith: "Connected To",
};

/**
 * Convert a predicate URI or local name to a human-readable label.
 */
export function humanizePredicate(pred: string): string {
  // Extract local name from full URI
  const local = pred.split("/").pop()?.split("#").pop() ?? pred;

  // Check known labels
  if (PREDICATE_LABELS[local]) return PREDICATE_LABELS[local];

  // Strip common prefixes, then camelCase → "Camel Case"
  return local
    .replace(/^has/, "")
    .replace(/^is([A-Z])/, "$1")  // isSex → Sex, isNobilis → Nobilis
    .replace(/([A-Z])/g, " $1")
    .replace(/^[\s]/, "")
    .trim() || local;
}

/**
 * Shorten a full predicate URI to prefix:localName form.
 */
export function shortenPredicate(pred: string): string {
  const prefixes: Record<string, string> = {
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://purl.org/dc/terms/": "dcterms:",
    "http://xmlns.com/foaf/0.1/": "foaf:",
    "http://nomisma.org/ontology#": "nmo:",
    "http://romanrepublic.ac.uk/rdf/ontology#": "vocab:",
  };
  for (const [ns, prefix] of Object.entries(prefixes)) {
    if (pred.startsWith(ns)) return prefix + pred.slice(ns.length);
  }
  return pred.split("/").pop()?.split("#").pop() ?? pred;
}
