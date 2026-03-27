"""Extract structured JSON data from the DPRR RDF dataset.

Usage:
    uv run python scripts/extract_data.py [path/to/dprr.ttl]

Loads the Turtle file into an ephemeral pyoxigraph Store, runs SPARQL queries,
and writes JSON files to data/extracted/.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from pyoxigraph import RdfFormat, Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TTL = ROOT / "data" / "dprr.ttl"
OUTPUT_DIR = ROOT / "data" / "extracted"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_prefix_map() -> dict[str, str]:
    """Load the SPARQL prefix map from the YAML config."""
    prefixes_path = ROOT / "dprr_mcp" / "context" / "prefixes.yaml"
    with open(prefixes_path) as f:
        data = yaml.safe_load(f)
    return data["prefixes"]


def sparql_prefixes(prefix_map: dict[str, str]) -> str:
    """Build a SPARQL PREFIX block from the prefix map."""
    return "\n".join(f"PREFIX {k}: <{v}>" for k, v in prefix_map.items())


def query_to_dicts(store: Store, sparql: str) -> list[dict[str, str | None]]:
    """Execute a SPARQL SELECT query and return results as a list of dicts.

    Uses results.variables to get variable names (iterating a QuerySolution
    yields values, not variable names).
    """
    results = store.query(sparql)
    variables = [v.value for v in results.variables]
    rows: list[dict[str, str | None]] = []
    for solution in results:
        row: dict[str, str | None] = {}
        for var_name in variables:
            value = solution[var_name]
            row[var_name] = value.value if value is not None else None
        rows.append(row)
    return rows


def slugify(name: str) -> str:
    """Lowercase name with spaces replaced by hyphens."""
    return re.sub(r"\s+", "-", name.strip().lower())


def strip_label_prefix(label: str | None) -> str | None:
    """Remove ontology label prefixes like 'Office: ', 'Sex: ', etc."""
    if label is None:
        return None
    for prefix in (
        "Office: ",
        "Sex: ",
        "Status: ",
        "Tribe: ",
        "Relationship: ",
        "Date Type: ",
        "Province: ",
        "Praenomen: ",
        "Secondary Source: ",
        "Primary Source: ",
    ):
        if label.startswith(prefix):
            return label[len(prefix) :]
    return label


def to_bool(val: str | None) -> bool:
    """Convert an RDF boolean string to Python bool. Absence = False."""
    return val == "true"


def to_int(val: str | None) -> int | None:
    """Convert an RDF integer string to Python int or None."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def load_store(ttl_path: Path) -> Store:
    """Create an ephemeral pyoxigraph Store and load a Turtle file."""
    store = Store()
    store.bulk_load(path=str(ttl_path), format=RdfFormat.TURTLE)
    return store


# ---------------------------------------------------------------------------
# Extraction: Persons
# ---------------------------------------------------------------------------


def extract_persons(store: Store, prefix_map: dict[str, str]) -> list[dict]:
    """Extract all persons with nested assertions."""
    pfx = sparql_prefixes(prefix_map)

    # --- Base person data ---
    person_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?dprrId ?personName ?praenomenName ?nomen ?cognomen ?filiation
       ?otherNames ?sexLabel ?eraFrom ?eraTo ?highestOffice ?reNumber
       ?origin ?patrician ?nobilis ?novus
       ?praenomenUncertain ?nomenUncertain ?cognomenUncertain
       ?filiationUncertain ?otherNamesUncertain ?patricianUncertain
WHERE {{
  ?person a vocab:Person ;
          vocab:hasDprrID ?dprrId .
  OPTIONAL {{ ?person vocab:hasPersonName ?personName }}
  OPTIONAL {{ ?person vocab:hasPraenomen ?prae . ?prae vocab:hasName ?praenomenName }}
  OPTIONAL {{ ?person vocab:hasNomen ?nomen }}
  OPTIONAL {{ ?person vocab:hasCognomen ?cognomen }}
  OPTIONAL {{ ?person vocab:hasFiliation ?filiation }}
  OPTIONAL {{ ?person vocab:hasOtherNames ?otherNames }}
  OPTIONAL {{ ?person vocab:isSex ?sex . ?sex rdfs:label ?sexLabel }}
  OPTIONAL {{ ?person vocab:hasEraFrom ?eraFrom }}
  OPTIONAL {{ ?person vocab:hasEraTo ?eraTo }}
  OPTIONAL {{ ?person vocab:hasHighestOffice ?highestOffice }}
  OPTIONAL {{ ?person vocab:hasReNumber ?reNumber }}
  OPTIONAL {{ ?person vocab:hasOrigin ?origin }}
  OPTIONAL {{ ?person vocab:isPatrician ?patrician }}
  OPTIONAL {{ ?person vocab:isNobilis ?nobilis }}
  OPTIONAL {{ ?person vocab:isNovus ?novus }}
  OPTIONAL {{ ?person vocab:isPraenomenUncertain ?praenomenUncertain }}
  OPTIONAL {{ ?person vocab:isNomenUncertain ?nomenUncertain }}
  OPTIONAL {{ ?person vocab:isCognomenUncertain ?cognomenUncertain }}
  OPTIONAL {{ ?person vocab:isFiliationUncertain ?filiationUncertain }}
  OPTIONAL {{ ?person vocab:isOtherNamesUncertain ?otherNamesUncertain }}
  OPTIONAL {{ ?person vocab:isPatricianUncertain ?patricianUncertain }}
}}
ORDER BY ?dprrId
""",
    )

    # Build person lookup
    persons: dict[str, dict] = {}
    for row in person_rows:
        pid = row["dprrId"]
        if pid in persons:
            continue  # deduplicate
        # Extract display name: strip the DPRR ID prefix from hasPersonName
        raw_name = row.get("personName") or ""
        # Name format: "IUNI0001 L. Iunius (46a, Supb. 5.356ff.) M. f. Brutus"
        display_name = raw_name[len(pid) :].strip() if raw_name.startswith(pid) else raw_name

        persons[pid] = {
            "id": pid,
            "name": display_name,
            "praenomen": row.get("praenomenName"),
            "nomen": row.get("nomen"),
            "cognomen": row.get("cognomen"),
            "filiation": row.get("filiation"),
            "eraFrom": to_int(row.get("eraFrom")),
            "eraTo": to_int(row.get("eraTo")),
            "sex": strip_label_prefix(row.get("sexLabel")),
            "patrician": to_bool(row.get("patrician")),
            "nobilis": to_bool(row.get("nobilis")),
            "novus": to_bool(row.get("novus")),
            "highestOffice": row.get("highestOffice"),
            "reNumber": row.get("reNumber"),
            "origin": row.get("origin"),
            "praenomenUncertain": to_bool(row.get("praenomenUncertain")),
            "nomenUncertain": to_bool(row.get("nomenUncertain")),
            "cognomenUncertain": to_bool(row.get("cognomenUncertain")),
            "filiationUncertain": to_bool(row.get("filiationUncertain")),
            "otherNamesUncertain": to_bool(row.get("otherNamesUncertain")),
            "patricianUncertain": to_bool(row.get("patricianUncertain")),
            "notes": [],
            "postAssertions": [],
            "relationships": [],
            "statusAssertions": [],
            "dateInformation": [],
            "tribeAssertions": [],
        }

    # --- Person notes ---
    note_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?dprrId ?noteText
WHERE {{
  ?person a vocab:Person ;
          vocab:hasDprrID ?dprrId ;
          vocab:hasPersonNote ?note .
  ?note vocab:hasNoteText ?noteText .
}}
""",
    )
    for row in note_rows:
        pid = row["dprrId"]
        if pid in persons and row.get("noteText"):
            persons[pid]["notes"].append(row["noteText"])

    # --- Post assertions ---
    pa_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?dprrId ?pa ?officeName ?officeLabel ?dateStart ?dateEnd
       ?uncertain ?dateStartUncertain ?dateEndUncertain
       ?sourceName ?sourceLabel
       ?dateSourceName ?dateSourceLabel
       ?noteText ?originalText
       ?provinceName ?provinceLabel ?provinceUncertain
WHERE {{
  ?pa a vocab:PostAssertion ;
      vocab:isAboutPerson ?person ;
      vocab:hasOffice ?office .
  ?person vocab:hasDprrID ?dprrId .
  OPTIONAL {{ ?office vocab:hasName ?officeName }}
  OPTIONAL {{ ?office rdfs:label ?officeLabel }}
  OPTIONAL {{ ?pa vocab:hasDateStart ?dateStart }}
  OPTIONAL {{ ?pa vocab:hasDateEnd ?dateEnd }}
  OPTIONAL {{ ?pa vocab:isUncertain ?uncertain }}
  OPTIONAL {{ ?pa vocab:isDateStartUncertain ?dateStartUncertain }}
  OPTIONAL {{ ?pa vocab:isDateEndUncertain ?dateEndUncertain }}
  OPTIONAL {{ ?pa vocab:hasSecondarySource ?source .
              OPTIONAL {{ ?source vocab:hasName ?sourceName }}
              OPTIONAL {{ ?source rdfs:label ?sourceLabel }} }}
  OPTIONAL {{ ?pa vocab:hasDateSecondarySource ?dateSource .
              OPTIONAL {{ ?dateSource vocab:hasName ?dateSourceName }}
              OPTIONAL {{ ?dateSource rdfs:label ?dateSourceLabel }} }}
  OPTIONAL {{ ?pa vocab:hasPostAssertionNote ?paNote .
              ?paNote vocab:hasNoteText ?noteText }}
  OPTIONAL {{ ?pa vocab:hasOriginalText ?originalText }}
  OPTIONAL {{ ?pap a vocab:PostAssertionProvince ;
                   vocab:hasPostAssertion ?pa ;
                   vocab:hasProvince ?prov .
              OPTIONAL {{ ?prov vocab:hasName ?provinceName }}
              OPTIONAL {{ ?prov rdfs:label ?provinceLabel }}
              OPTIONAL {{ ?pap vocab:isProvinceUncertain ?provinceUncertain }} }}
}}
ORDER BY ?dprrId ?pa
""",
    )

    # Group PA rows by (dprrId, pa URI) since sources/notes can create multiple rows
    pa_grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in pa_rows:
        pid = row["dprrId"]
        pa_uri = row["pa"]
        if pa_uri not in pa_grouped[pid]:
            office_name = row.get("officeName") or strip_label_prefix(row.get("officeLabel"))
            province_name = row.get("provinceName") or strip_label_prefix(row.get("provinceLabel"))
            pa_grouped[pid][pa_uri] = {
                "office": office_name,
                "officeId": slugify(office_name) if office_name else None,
                "dateStart": to_int(row.get("dateStart")),
                "dateEnd": to_int(row.get("dateEnd")),
                "province": province_name,
                "provinceUncertain": to_bool(row.get("provinceUncertain")),
                "uncertain": to_bool(row.get("uncertain")),
                "dateStartUncertain": to_bool(row.get("dateStartUncertain")),
                "dateEndUncertain": to_bool(row.get("dateEndUncertain")),
                "sources": [],
                "dateSource": None,
                "notes": [],
                "originalText": row.get("originalText"),
                "_source_ids": set(),
            }
        pa_entry = pa_grouped[pid][pa_uri]

        # Collect sources (deduplicate)
        src_name = row.get("sourceName") or strip_label_prefix(row.get("sourceLabel"))
        if src_name and src_name not in pa_entry["_source_ids"]:
            pa_entry["_source_ids"].add(src_name)
            pa_entry["sources"].append({"name": src_name, "id": slugify(src_name)})

        # Date source
        ds_name = row.get("dateSourceName") or strip_label_prefix(row.get("dateSourceLabel"))
        if ds_name and pa_entry["dateSource"] is None:
            pa_entry["dateSource"] = ds_name

        # Notes
        note = row.get("noteText")
        if note and note not in pa_entry["notes"]:
            pa_entry["notes"].append(note)

    for pid, pa_map in pa_grouped.items():
        if pid in persons:
            for pa_entry in pa_map.values():
                del pa_entry["_source_ids"]
                persons[pid]["postAssertions"].append(pa_entry)

    # --- Relationships ---
    rel_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?dprrId ?relLabel ?relatedDprrId ?relatedName
WHERE {{
  ?ra a vocab:RelationshipAssertion ;
      vocab:isAboutPerson ?person ;
      vocab:hasRelationship ?rel ;
      vocab:hasRelatedPerson ?related .
  ?person vocab:hasDprrID ?dprrId .
  ?rel rdfs:label ?relLabel .
  OPTIONAL {{ ?related vocab:hasDprrID ?relatedDprrId }}
  OPTIONAL {{ ?related vocab:hasPersonName ?relatedName }}
}}
""",
    )
    for row in rel_rows:
        pid = row["dprrId"]
        if pid in persons:
            related_id = row.get("relatedDprrId")
            raw_related_name = row.get("relatedName") or ""
            # Strip DPRR ID prefix from display name
            if related_id and raw_related_name.startswith(related_id):
                related_display = raw_related_name[len(related_id) :].strip()
            else:
                related_display = raw_related_name or None
            persons[pid]["relationships"].append(
                {
                    "type": strip_label_prefix(row.get("relLabel")),
                    "relatedPersonId": related_id,
                    "relatedPersonName": related_display,
                }
            )

    # --- Status assertions ---
    sa_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?dprrId ?statusLabel ?dateStart ?dateEnd
       ?uncertain ?dateStartUncertain ?dateEndUncertain
       ?sourceName ?sourceLabel ?noteText ?originalText
WHERE {{
  ?sa a vocab:StatusAssertion ;
      vocab:isAboutPerson ?person ;
      vocab:hasStatus ?status .
  ?person vocab:hasDprrID ?dprrId .
  ?status rdfs:label ?statusLabel .
  OPTIONAL {{ ?sa vocab:hasDateStart ?dateStart }}
  OPTIONAL {{ ?sa vocab:hasDateEnd ?dateEnd }}
  OPTIONAL {{ ?sa vocab:isUncertain ?uncertain }}
  OPTIONAL {{ ?sa vocab:isDateStartUncertain ?dateStartUncertain }}
  OPTIONAL {{ ?sa vocab:isDateEndUncertain ?dateEndUncertain }}
  OPTIONAL {{ ?sa vocab:hasSecondarySource ?source .
              OPTIONAL {{ ?source vocab:hasName ?sourceName }}
              OPTIONAL {{ ?source rdfs:label ?sourceLabel }} }}
  OPTIONAL {{ ?sa vocab:hasStatusAssertionNote ?saNote .
              ?saNote vocab:hasNoteText ?noteText }}
  OPTIONAL {{ ?sa vocab:hasOriginalText ?originalText }}
}}
""",
    )
    for row in sa_rows:
        pid = row["dprrId"]
        if pid in persons:
            src_name = row.get("sourceName") or strip_label_prefix(row.get("sourceLabel"))
            sources = [{"name": src_name, "id": slugify(src_name)}] if src_name else []
            notes = [row["noteText"]] if row.get("noteText") else []
            persons[pid]["statusAssertions"].append(
                {
                    "status": strip_label_prefix(row.get("statusLabel")),
                    "dateStart": to_int(row.get("dateStart")),
                    "dateEnd": to_int(row.get("dateEnd")),
                    "uncertain": to_bool(row.get("uncertain")),
                    "dateStartUncertain": to_bool(row.get("dateStartUncertain")),
                    "dateEndUncertain": to_bool(row.get("dateEndUncertain")),
                    "sources": sources,
                    "notes": notes,
                    "originalText": row.get("originalText"),
                }
            )

    # --- Date information ---
    di_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?dprrId ?dateTypeLabel ?value ?interval ?uncertain
       ?sourceName ?sourceLabel
WHERE {{
  ?di a vocab:DateInformation ;
      vocab:isAboutPerson ?person ;
      vocab:hasDateType ?dt .
  ?person vocab:hasDprrID ?dprrId .
  ?dt rdfs:label ?dateTypeLabel .
  OPTIONAL {{ ?di vocab:hasValue ?value }}
  OPTIONAL {{ ?di vocab:hasDateInterval ?interval }}
  OPTIONAL {{ ?di vocab:isUncertain ?uncertain }}
  OPTIONAL {{ ?di vocab:hasSecondarySource ?source .
              OPTIONAL {{ ?source vocab:hasName ?sourceName }}
              OPTIONAL {{ ?source rdfs:label ?sourceLabel }} }}
}}
""",
    )
    for row in di_rows:
        pid = row["dprrId"]
        if pid in persons:
            src_name = row.get("sourceName") or strip_label_prefix(row.get("sourceLabel"))
            persons[pid]["dateInformation"].append(
                {
                    "type": strip_label_prefix(row.get("dateTypeLabel")),
                    "value": to_int(row.get("value")),
                    "interval": row.get("interval"),
                    "uncertain": to_bool(row.get("uncertain")),
                    "source": src_name,
                }
            )

    # --- Tribe assertions ---
    ta_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?dprrId ?tribeLabel ?uncertain ?sourceName ?sourceLabel
WHERE {{
  ?ta a vocab:TribeAssertion ;
      vocab:isAboutPerson ?person ;
      vocab:hasTribe ?tribe .
  ?person vocab:hasDprrID ?dprrId .
  ?tribe rdfs:label ?tribeLabel .
  OPTIONAL {{ ?ta vocab:isUncertain ?uncertain }}
  OPTIONAL {{ ?ta vocab:hasSecondarySource ?source .
              OPTIONAL {{ ?source vocab:hasName ?sourceName }}
              OPTIONAL {{ ?source rdfs:label ?sourceLabel }} }}
}}
""",
    )
    for row in ta_rows:
        pid = row["dprrId"]
        if pid in persons:
            src_name = row.get("sourceName") or strip_label_prefix(row.get("sourceLabel"))
            persons[pid]["tribeAssertions"].append(
                {
                    "tribe": strip_label_prefix(row.get("tribeLabel")),
                    "uncertain": to_bool(row.get("uncertain")),
                    "source": src_name,
                }
            )

    return sorted(persons.values(), key=lambda p: p["id"])


# ---------------------------------------------------------------------------
# Extraction: Offices
# ---------------------------------------------------------------------------


def extract_offices(store: Store, prefix_map: dict[str, str]) -> list[dict]:
    """Extract all offices with hierarchy and holder lists."""
    pfx = sparql_prefixes(prefix_map)

    # --- Office base data ---
    office_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?office ?officeName ?officeLabel ?abbreviation
       ?parentOffice ?parentName ?parentLabel
WHERE {{
  ?office a vocab:Office .
  OPTIONAL {{ ?office vocab:hasName ?officeName }}
  OPTIONAL {{ ?office rdfs:label ?officeLabel }}
  OPTIONAL {{ ?office vocab:hasAbbreviation ?abbreviation }}
  OPTIONAL {{ ?office vocab:hasParent ?parentOffice .
              OPTIONAL {{ ?parentOffice vocab:hasName ?parentName }}
              OPTIONAL {{ ?parentOffice rdfs:label ?parentLabel }} }}
}}
ORDER BY ?officeName
""",
    )

    offices: dict[str, dict] = {}
    office_uri_to_id: dict[str, str] = {}

    for row in office_rows:
        name = row.get("officeName") or strip_label_prefix(row.get("officeLabel"))
        if not name:
            continue
        oid = slugify(name)
        if oid in offices:
            continue
        office_uri_to_id[row["office"]] = oid
        parent_name = row.get("parentName") or strip_label_prefix(row.get("parentLabel"))
        offices[oid] = {
            "id": oid,
            "name": name,
            "abbreviation": row.get("abbreviation"),
            "parentId": slugify(parent_name) if parent_name else None,
            "parentName": parent_name,
            "children": [],
            "holders": [],
        }

    # Build children lists
    for oid, office in offices.items():
        parent_id = office["parentId"]
        if parent_id and parent_id in offices:
            offices[parent_id]["children"].append({"id": oid, "name": office["name"]})

    # --- Holders (from post assertions) ---
    holder_rows = query_to_dicts(
        store,
        f"""{pfx}
SELECT ?officeName ?officeLabel ?dprrId ?personName
       ?dateStart ?dateEnd ?uncertain ?dateStartUncertain ?dateEndUncertain
       ?sourceName ?sourceLabel
WHERE {{
  ?pa a vocab:PostAssertion ;
      vocab:isAboutPerson ?person ;
      vocab:hasOffice ?office .
  ?person vocab:hasDprrID ?dprrId .
  OPTIONAL {{ ?person vocab:hasPersonName ?personName }}
  OPTIONAL {{ ?office vocab:hasName ?officeName }}
  OPTIONAL {{ ?office rdfs:label ?officeLabel }}
  OPTIONAL {{ ?pa vocab:hasDateStart ?dateStart }}
  OPTIONAL {{ ?pa vocab:hasDateEnd ?dateEnd }}
  OPTIONAL {{ ?pa vocab:isUncertain ?uncertain }}
  OPTIONAL {{ ?pa vocab:isDateStartUncertain ?dateStartUncertain }}
  OPTIONAL {{ ?pa vocab:isDateEndUncertain ?dateEndUncertain }}
  OPTIONAL {{ ?pa vocab:hasSecondarySource ?source .
              OPTIONAL {{ ?source vocab:hasName ?sourceName }}
              OPTIONAL {{ ?source rdfs:label ?sourceLabel }} }}
}}
ORDER BY ?officeName ?dateStart ?dprrId
""",
    )

    # Group holders, dedup sources per (office, person, dateStart)
    for row in holder_rows:
        office_name = row.get("officeName") or strip_label_prefix(row.get("officeLabel"))
        if not office_name:
            continue
        oid = slugify(office_name)
        if oid not in offices:
            continue

        pid = row["dprrId"]
        raw_name = row.get("personName") or ""
        display_name = raw_name[len(pid) :].strip() if raw_name.startswith(pid) else raw_name

        src_name = row.get("sourceName") or strip_label_prefix(row.get("sourceLabel"))
        sources = [{"name": src_name, "id": slugify(src_name)}] if src_name else []

        offices[oid]["holders"].append(
            {
                "personId": pid,
                "personName": display_name,
                "dateStart": to_int(row.get("dateStart")),
                "dateEnd": to_int(row.get("dateEnd")),
                "uncertain": to_bool(row.get("uncertain")),
                "dateStartUncertain": to_bool(row.get("dateStartUncertain")),
                "dateEndUncertain": to_bool(row.get("dateEndUncertain")),
                "sources": sources,
            }
        )

    return sorted(offices.values(), key=lambda o: o["id"])


# ---------------------------------------------------------------------------
# Search Index
# ---------------------------------------------------------------------------


def build_search_index(persons: list[dict], offices: list[dict]) -> list[dict]:
    """Build a flat search index from persons and offices."""
    index: list[dict] = []

    for p in persons:
        era_from = p.get("eraFrom")
        era_to = p.get("eraTo")
        if era_from is not None and era_to is not None:
            era = f"{era_from} to {era_to}"
        elif era_from is not None:
            era = str(era_from)
        elif era_to is not None:
            era = str(era_to)
        else:
            era = None

        index.append(
            {
                "id": p["id"],
                "type": "person",
                "name": p["name"],
                "nomen": p.get("nomen"),
                "cognomen": p.get("cognomen"),
                "praenomen": p.get("praenomen"),
                "highestOffice": p.get("highestOffice"),
                "era": era,
            }
        )

    for o in offices:
        index.append(
            {
                "id": o["id"],
                "type": "office",
                "name": o["name"],
                "abbreviation": o.get("abbreviation"),
            }
        )

    return index


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: load TTL, extract data, write JSON files."""
    ttl_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TTL

    if not ttl_path.exists():
        print(f"Error: {ttl_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {ttl_path} ...")
    store = load_store(ttl_path)
    print(f"Loaded {len(store)} triples")

    prefix_map = load_prefix_map()

    print("Extracting persons ...")
    persons = extract_persons(store, prefix_map)
    print(f"  {len(persons)} persons")

    print("Extracting offices ...")
    offices = extract_offices(store, prefix_map)
    print(f"  {len(offices)} offices")

    print("Building search index ...")
    search_index = build_search_index(persons, offices)
    print(f"  {len(search_index)} entries")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, data in [
        ("persons.json", persons),
        ("offices.json", offices),
        ("search-index.json", search_index),
    ]:
        out_path = OUTPUT_DIR / name
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Wrote {out_path} ({len(data)} records)")

    print("Done.")


if __name__ == "__main__":
    main()
