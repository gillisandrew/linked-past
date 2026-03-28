import type { Person, Office, PersonIndex, OfficeIndex, SearchDoc } from "./types";

import personsIndex from "../../../data/extracted/persons-index.json";
import officesIndex from "../../../data/extracted/offices-index.json";
import searchData from "../../../data/extracted/search-index.json";

const personsIdx = personsIndex as PersonIndex[];
const officesIdx = officesIndex as OfficeIndex[];
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

export function getSearchIndex(): SearchDoc[] {
  return searchIdx;
}
