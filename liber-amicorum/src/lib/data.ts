import type {
  Person,
  Office,
  PersonIndex,
  OfficeIndex,
  SearchDoc,
  OfficeHolderWithOffice,
  SourceIndex,
  SourceDetail,
  NetworkData,
} from "./types";

import personsIndex from "../../../data/extracted/persons-index.json";
import officesIndex from "../../../data/extracted/offices-index.json";
import sourcesIndex from "../../../data/extracted/sources-index.json";
import searchData from "../../../data/extracted/search-index.json";

const personsIdx = personsIndex as PersonIndex[];
const officesIdx = officesIndex as OfficeIndex[];
const sourcesIdx = sourcesIndex as SourceIndex[];
const searchIdx = searchData as SearchDoc[];

export function getPersonsIndex(): PersonIndex[] {
  return personsIdx;
}

export function getOfficesIndex(): OfficeIndex[] {
  return officesIdx;
}

export async function getPersonById(id: string): Promise<Person | undefined> {
  try {
    const mod = await import(`../../../data/extracted/persons/${id}.json`);
    return mod.default as Person;
  } catch {
    return undefined;
  }
}

export async function getOfficeById(id: string): Promise<Office | undefined> {
  try {
    const mod = await import(`../../../data/extracted/offices/${id}.json`);
    return mod.default as Office;
  } catch {
    return undefined;
  }
}

export function getSourcesIndex(): SourceIndex[] {
  return sourcesIdx;
}

export async function getSourceById(id: string): Promise<SourceDetail | undefined> {
  try {
    const mod = await import(`../../../data/extracted/sources/${id}.json`);
    return mod.default as SourceDetail;
  } catch {
    return undefined;
  }
}

export function getSearchIndex(): SearchDoc[] {
  return searchIdx;
}

export async function getNetworkData(): Promise<NetworkData> {
  const mod = await import("../../../data/extracted/relationships.json");
  return mod.default as NetworkData;
}

export interface OfficeWithMergedHolders extends Office {
  allHolders: OfficeHolderWithOffice[];
  subOfficeNames: { id: string; name: string }[];
}

/**
 * Load an office and merge holders from all child offices.
 * Each holder is tagged with the specific office it belongs to.
 */
export async function getOfficeWithDescendants(
  id: string,
): Promise<OfficeWithMergedHolders | undefined> {
  const office = await getOfficeById(id);
  if (!office) return undefined;

  const allHolders: OfficeHolderWithOffice[] = office.holders.map((h) => ({
    ...h,
    officeName: office.name,
    officeId: office.id,
  }));

  const subOfficeNames: { id: string; name: string }[] = [];

  // Load all child offices and merge their holders
  for (const child of office.children) {
    const childOffice = await getOfficeById(child.id);
    if (childOffice) {
      subOfficeNames.push({ id: childOffice.id, name: childOffice.name });
      for (const h of childOffice.holders) {
        allHolders.push({
          ...h,
          officeName: childOffice.name,
          officeId: childOffice.id,
        });
      }
    }
  }

  // Sort all holders by date
  allHolders.sort((a, b) => (a.dateStart ?? 0) - (b.dateStart ?? 0));

  return { ...office, allHolders, subOfficeNames };
}
