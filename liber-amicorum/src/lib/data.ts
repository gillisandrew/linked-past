import type { Person, Office, SearchDoc } from "./types";

import personsData from "../../../data/extracted/persons.json";
import officesData from "../../../data/extracted/offices.json";
import searchData from "../../../data/extracted/search-index.json";

const persons = personsData as Person[];
const offices = officesData as Office[];
const searchIndex = searchData as SearchDoc[];

const personById = new Map(persons.map((p) => [p.id, p]));
const officeById = new Map(offices.map((o) => [o.id, o]));

export function getAllPersons(): Person[] {
  return persons;
}

export function getPersonById(id: string): Person | undefined {
  return personById.get(id);
}

export function getAllOffices(): Office[] {
  return offices;
}

export function getOfficeById(id: string): Office | undefined {
  return officeById.get(id);
}

export function getSearchIndex(): SearchDoc[] {
  return searchIndex;
}
