import MiniSearch from "minisearch";
import type { SearchDoc } from "./types";
import { getSearchIndex } from "./data";

let searchInstance: MiniSearch<SearchDoc> | null = null;

export function getSearch(): MiniSearch<SearchDoc> {
  if (searchInstance) return searchInstance;

  searchInstance = new MiniSearch<SearchDoc>({
    fields: ["name", "nomen", "cognomen", "praenomen", "abbreviation", "reNumber", "dprrId"],
    storeFields: [
      "id",
      "type",
      "name",
      "nomen",
      "highestOffice",
      "era",
      "abbreviation",
      "reNumber",
    ],
    searchOptions: {
      boost: { nomen: 2, cognomen: 2 },
      fuzzy: 0.2,
      prefix: true,
    },
  });

  searchInstance.addAll(getSearchIndex());
  return searchInstance;
}

export interface SearchResult {
  id: string;
  type: "person" | "office";
  name: string;
  nomen?: string;
  highestOffice?: string;
  era?: string;
  abbreviation?: string;
}

export function search(query: string): SearchResult[] {
  if (!query.trim()) return [];
  return getSearch().search(query) as unknown as SearchResult[];
}
