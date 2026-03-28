export interface Source {
  name: string;
  id: string;
}

export interface PostAssertion {
  office: string;
  officeId: string;
  dateStart: number | null;
  dateEnd: number | null;
  province: string | null;
  provinceUncertain: boolean;
  uncertain: boolean;
  dateStartUncertain: boolean;
  dateEndUncertain: boolean;
  sources: Source[];
  dateSource: Source | null;
  notes: string[];
  originalText: string | null;
}

export interface Relationship {
  type: string;
  relatedPersonId: string | null;
  relatedPersonName: string | null;
}

export interface StatusAssertion {
  status: string;
  dateStart: number | null;
  dateEnd: number | null;
  uncertain: boolean;
  dateStartUncertain: boolean;
  dateEndUncertain: boolean;
  sources: Source[];
  notes: string[];
  originalText: string | null;
}

export interface DateInfo {
  type: string;
  value: number | null;
  interval: string | null;
  uncertain: boolean;
  source: Source | null;
}

export interface TribeAssertion {
  tribe: string;
  uncertain: boolean;
  source: Source | null;
}

export interface Person {
  id: string;
  name: string;
  praenomen: string | null;
  nomen: string | null;
  cognomen: string | null;
  filiation: string | null;
  eraFrom: number | null;
  eraTo: number | null;
  sex: string | null;
  patrician: boolean;
  nobilis: boolean;
  novus: boolean;
  highestOffice: string | null;
  reNumber: string | null;
  origin: string | null;
  praenomenUncertain: boolean;
  nomenUncertain: boolean;
  cognomenUncertain: boolean;
  filiationUncertain: boolean;
  otherNamesUncertain: boolean;
  patricianUncertain: boolean;
  notes: string[];
  postAssertions: PostAssertion[];
  relationships: Relationship[];
  statusAssertions: StatusAssertion[];
  dateInformation: DateInfo[];
  tribeAssertions: TribeAssertion[];
}

export interface OfficeChild {
  id: string;
  name: string;
}

export interface OfficeHolder {
  personId: string;
  personName: string;
  dateStart: number | null;
  dateEnd: number | null;
  uncertain: boolean;
  dateStartUncertain: boolean;
  dateEndUncertain: boolean;
  sources: Source[];
}

/** OfficeHolder extended with the office it belongs to (for merged parent+child views) */
export interface OfficeHolderWithOffice extends OfficeHolder {
  officeName: string;
  officeId: string;
}

export interface Office {
  id: string;
  name: string;
  abbreviation: string | null;
  parentId: string | null;
  parentName: string | null;
  children: OfficeChild[];
  holders: OfficeHolder[];
}

export interface PersonIndex {
  id: string;
  name: string;
  nomen: string | null;
  cognomen: string | null;
  praenomen: string | null;
  eraFrom: number | null;
  eraTo: number | null;
  sex: string | null;
  highestOffice: string | null;
  patrician: boolean;
  nobilis: boolean;
  novus: boolean;
  origin: string | null;
  patricianUncertain: boolean;
}

export interface OfficeIndex {
  id: string;
  name: string;
  abbreviation: string | null;
  parentId: string | null;
  parentName: string | null;
  holderCount: number;
  children: OfficeChild[];
}

export interface OfficeTreeNode extends OfficeIndex {
  subOffices: OfficeTreeNode[];
}

export interface SourceCitation {
  personId: string;
  personName: string;
  context: string;
  anchor: string;
}

export interface SourceDetail {
  id: string;
  abbreviation: string;
  name: string | null;
  biblio: string | null;
  notes: string[];
  citations: SourceCitation[];
}

export interface SourceIndex {
  id: string;
  abbreviation: string;
  name: string | null;
  citationCount: number;
}

export interface SearchDoc {
  id: string;
  type: "person" | "office";
  name: string;
  nomen?: string;
  cognomen?: string;
  praenomen?: string;
  highestOffice?: string;
  era?: string;
  abbreviation?: string;
}
