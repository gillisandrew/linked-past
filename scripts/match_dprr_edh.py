"""Match DPRR persons to EDH inscription persons by name.

Focuses on EDH persons of senatorial or equestrian order, matching
against DPRR persons by nomen + cognomen + praenomen agreement.
Includes Greek→Latin transliteration for bilingual inscriptions.

Usage:
    uv run python scripts/match_dprr_edh.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml
from linked_past.core.onomastics import GREEK_PRAENOMINA, PRAENOMEN_MAP
from linked_past.core.onomastics import normalize_edh_name as _normalize_edh_name
from linked_past.core.onomastics import parse_roman_name as _parse_roman_name_base
from linked_past.core.onomastics import strip_accents as _strip_accents
from pyoxigraph import Store

DATA_DIR = Path.home() / ".local" / "share" / "linked-past"
LINKAGE_DIR = Path(__file__).resolve().parents[1] / "packages" / "linked-past" / "linked_past" / "linkages"

# Aliases for backwards compatibility within this script
_PRAENOMEN_MAP = PRAENOMEN_MAP
_GREEK_PRAENOMINA = GREEK_PRAENOMINA


def _parse_roman_name(name: str) -> dict:
    """Wrapper around onomastics.parse_roman_name for script use."""
    return _parse_roman_name_base(name)


def _open_store(dataset: str) -> Store:
    path = DATA_DIR / dataset / "store"
    return Store.read_only(str(path))


def _query_all(store: Store, sparql: str) -> list[dict]:
    results = store.query(sparql)
    variables = [v.value for v in results.variables]
    rows = []
    for solution in results:
        row = {}
        for var in variables:
            val = solution[var]
            row[var] = val.value if val is not None else None
        rows.append(row)
    return rows




def get_dprr_persons(store: Store) -> list[dict]:
    """Get all DPRR persons with structured name components."""
    rows = _query_all(store, """
        PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?person ?label ?nomen ?cognomen ?praenomenLabel
               ?eraFrom ?eraTo ?highestOffice WHERE {
          ?person a vocab:Person ;
                  rdfs:label ?label ;
                  vocab:hasNomen ?nomen .
          OPTIONAL { ?person vocab:hasCognomen ?cognomen }
          OPTIONAL { ?person vocab:hasPraenomen ?prae . ?prae rdfs:label ?praenomenLabel }
          OPTIONAL { ?person vocab:hasEraFrom ?eraFrom }
          OPTIONAL { ?person vocab:hasEraTo ?eraTo }
          OPTIONAL { ?person vocab:hasHighestOffice ?highestOffice }
        }
    """)
    # Deduplicate by person URI
    by_uri = {}
    for r in rows:
        uri = r["person"]
        if uri not in by_uri:
            by_uri[uri] = r
    return list(by_uri.values())


def get_edh_elite_persons(store: Store) -> list[dict]:
    """Get EDH persons of senatorial or equestrian order."""
    rows = _query_all(store, """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX lawd: <http://lawd.info/ontology/Person>
        SELECT ?person ?name ?status ?inscription WHERE {
          ?person a <http://lawd.info/ontology/Person> ;
                  foaf:name ?name .
          OPTIONAL {
            ?person foaf:member ?statusUri .
            BIND(STR(?statusUri) AS ?status)
          }
          OPTIONAL {
            ?person <http://lawd.info/ontology/hasAttestation> ?att .
            BIND(REPLACE(STR(?att), "#ref$", "") AS ?inscription)
          }
          FILTER EXISTS {
            ?person foaf:member ?s .
            FILTER(?s IN (
              <https://edh-www.adw.uni-heidelberg.de/edh/social_status/senatorial_order>,
              <https://edh-www.adw.uni-heidelberg.de/edh/social_status/equestrian_order>
            ))
          }
        }
    """)
    # Deduplicate by person URI, keep first name
    by_uri = {}
    for r in rows:
        uri = r["person"]
        if uri not in by_uri:
            by_uri[uri] = r
    return list(by_uri.values())


def match_candidates(
    dprr_persons: list[dict],
    edh_persons: list[dict],
) -> list[dict]:
    """Match DPRR persons to EDH persons by name components."""
    # Build nomen index for DPRR
    dprr_by_nomen: dict[str, list[dict]] = {}
    for d in dprr_persons:
        nomen = d.get("nomen", "").strip("() ").lower()
        nomen = re.sub(r"[()]", "", nomen).strip()
        if nomen and len(nomen) > 2:
            dprr_by_nomen.setdefault(nomen, []).append(d)

    # Parse EDH names and match
    candidates = []
    greek_matches = 0
    for edh in edh_persons:
        name = edh.get("name", "")
        if not name or len(name) < 5:
            continue

        # Transliterate Greek names to Latin
        normalized_name, was_greek = _normalize_edh_name(name)

        # Greek praenomen lookup handled in name parsing below

        parsed = _parse_roman_name(normalized_name)
        edh_nomen = (parsed.get("nomen") or "").lower()
        edh_cog = (parsed.get("cognomen") or "").lower()
        edh_prae = parsed.get("praenomen")

        # For Greek names, override praenomen from the Greek lookup if available
        if was_greek and not edh_prae:
            first_word = _strip_accents(name.split()[0].lower()) if name.split() else ""
            edh_prae = _GREEK_PRAENOMINA.get(first_word)

        if not edh_nomen or len(edh_nomen) < 3:
            continue

        # Look for DPRR matches by nomen
        dprr_matches = dprr_by_nomen.get(edh_nomen, [])
        # Also try -ius → -ia variation (for women)
        if edh_nomen.endswith("ia"):
            masc = edh_nomen[:-1] + "us"
            dprr_matches = dprr_matches + dprr_by_nomen.get(masc, [])

        for dprr in dprr_matches:
            dprr_cog = (dprr.get("cognomen") or "").lower().strip("() []")
            dprr_prae_label = (dprr.get("praenomenLabel") or "").lower()
            dprr_prae = _PRAENOMEN_MAP.get(dprr_prae_label.split(":")[-1].strip().lower().rstrip("."))

            score = 0
            reasons = []

            # Nomen match (guaranteed by lookup)
            score += 1
            reasons.append("nomen")

            # Praenomen match
            if edh_prae and dprr_prae:
                if edh_prae == dprr_prae:
                    score += 2
                    reasons.append("praenomen")
                else:
                    # Praenomen mismatch — strong negative signal
                    continue

            # Cognomen match
            if edh_cog and dprr_cog:
                if edh_cog == dprr_cog:
                    score += 2
                    reasons.append("cognomen")
                elif edh_cog in dprr_cog or dprr_cog in edh_cog:
                    score += 1
                    reasons.append("cognomen~")
                else:
                    # Cognomen mismatch with both present
                    continue

            # Require at least praenomen+nomen+cognomen (score >= 5)
            if score >= 5:
                if was_greek:
                    reasons.append("greek")
                    greek_matches += 1
                candidates.append({
                    "dprr_uri": dprr["person"],
                    "edh_uri": edh["person"],
                    "dprr_label": dprr["label"],
                    "edh_name": name,
                    "edh_normalized": normalized_name if was_greek else None,
                    "edh_inscription": edh.get("inscription"),
                    "dprr_era": f"{dprr.get('eraFrom', '?')} to {dprr.get('eraTo', '?')}",
                    "dprr_office": dprr.get("highestOffice", ""),
                    "score": score,
                    "reasons": "+".join(reasons),
                    "was_greek": was_greek,
                })

    # Sort by score descending
    candidates.sort(key=lambda c: (-c["score"], c["dprr_label"]))

    if greek_matches:
        print(f"    ({greek_matches} matches via Greek transliteration)")

    return candidates


def main():
    print("Opening stores...")
    dprr_store = _open_store("dprr")
    edh_store = _open_store("edh")

    print("Querying DPRR persons...")
    dprr_persons = get_dprr_persons(dprr_store)
    print(f"  {len(dprr_persons)} persons")

    print("Querying EDH senatorial/equestrian persons...")
    edh_persons = get_edh_elite_persons(edh_store)
    print(f"  {len(edh_persons)} elite persons")

    # Load existing confirmed links
    conf_path = LINKAGE_DIR / "dprr_edh_confirmed.yaml"
    existing_pairs: set[tuple[str, str]] = set()
    if conf_path.exists():
        with conf_path.open() as f:
            conf_data = yaml.safe_load(f)
        existing_pairs = {(lnk["source"], lnk["target"]) for lnk in conf_data.get("links", [])}
        print(f"  {len(existing_pairs)} existing confirmed links")

    print("Matching candidates...")
    candidates = match_candidates(dprr_persons, edh_persons)
    print(f"  {len(candidates)} raw matches (score >= 5)")

    # Remove already-confirmed pairs
    candidates = [c for c in candidates if (c["dprr_uri"], c["edh_uri"]) not in existing_pairs]
    print(f"  {len(candidates)} after excluding already-confirmed")

    # Separate Greek-origin matches
    greek_cands = [c for c in candidates if c.get("was_greek")]
    if greek_cands:
        print(f"  {len(greek_cands)} from Greek transliteration")

    # Filter to safe 1:1 matches
    dprr_counts = Counter(c["dprr_uri"] for c in candidates)
    edh_counts = Counter(c["edh_uri"] for c in candidates)
    safe = [c for c in candidates if dprr_counts[c["dprr_uri"]] == 1 and edh_counts[c["edh_uri"]] == 1]
    ambiguous = [c for c in candidates if c not in safe]

    safe_greek = [c for c in safe if c.get("was_greek")]
    safe_latin = [c for c in safe if not c.get("was_greek")]

    print(f"  {len(safe)} safe 1:1 matches ({len(safe_greek)} Greek, {len(safe_latin)} Latin)")
    print(f"  {len(ambiguous)} ambiguous (1:many or many:1)")

    # Print safe matches
    if safe:
        print(f"\n{'=' * 140}")
        hdr = f"{'Score':>5}  {'Src':>5}  {'DPRR Label':<50}  {'EDH Name':<35}"
        print(hdr)
        print("-" * len(hdr))
        for c in safe:
            src = "GRK" if c.get("was_greek") else "LAT"
            print(f"{c['score']:>5}  {src:>5}  {c['dprr_label'][:50]:<50}  {c['edh_name'][:35]}")

    # Merge safe matches into confirmed file
    if safe:
        if conf_path.exists():
            with conf_path.open() as f:
                conf_data = yaml.safe_load(f)
        else:
            conf_data = {
                "metadata": {
                    "source_dataset": "dprr",
                    "target_dataset": "edh",
                    "relationship": "skos:closeMatch",
                    "confidence": "confirmed",
                    "method": "automated_name_matching",
                    "basis": (
                    "Praenomen + nomen + cognomen matching between DPRR persons"
                    " and EDH senatorial/equestrian persons, incl. Greek transliteration"
                ),
                    "author": "linked-past project",
                    "date": "2026-03-30",
                },
                "links": [],
            }

        existing_in_file = {(lnk["source"], lnk["target"]) for lnk in conf_data["links"]}
        added = 0
        for c in safe:
            pair = (c["dprr_uri"], c["edh_uri"])
            if pair not in existing_in_file:
                note = f"DPRR: {c['dprr_label'][:60]}; EDH: {c['edh_name']}; {c['dprr_office']}"
                if c.get("was_greek"):
                    note += f"; Greek transliteration → {c.get('edh_normalized', '')}"
                conf_data["links"].append({
                    "source": c["dprr_uri"],
                    "target": c["edh_uri"],
                    "note": note,
                })
                added += 1

        with conf_path.open("w") as f:
            yaml.dump(conf_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"\nAdded {added} new links to {conf_path}")
        print(f"Total confirmed DPRR→EDH links: {len(conf_data['links'])}")

    # Print Greek matches for review (even ambiguous ones are interesting)
    if greek_cands:
        print(f"\n{'=' * 140}")
        print("ALL GREEK TRANSLITERATION MATCHES (including ambiguous):")
        print(f"{'=' * 140}")
        print(f"{'Score':>5}  {'DPRR Label':<50}  {'EDH Greek Name':<35}  {'Transliterated':<25}  {'1:1?':<5}")
        print(f"{'-' * 140}")
        for c in greek_cands:
            is_safe = c in safe
            safe_flag = "YES" if is_safe else "no"
            print(f"{c['score']:>5}  {c['dprr_label'][:50]:<50}  {c['edh_name'][:35]:<35}  {safe_flag}")

    # Write ambiguous for review (skip writing file to avoid clutter)
    if ambiguous:
        review_path = LINKAGE_DIR / "dprr_edh_candidates.yaml"
        yaml_data = {
            "metadata": {
                "source_dataset": "dprr",
                "target_dataset": "edh",
                "relationship": "skos:closeMatch",
                "confidence": "candidate",
                "method": "automated_name_matching",
                "basis": "Praenomen + nomen + cognomen matching — ambiguous (1:many or many:1), needs manual review",
                "author": "linked-past project",
                "date": "2026-03-30",
            },
            "links": [
                {
                    "source": c["dprr_uri"],
                    "target": c["edh_uri"],
                    "note": f"DPRR: {c['dprr_label'][:60]}; EDH: {c['edh_name']}; {c['dprr_office']}",
                }
                for c in ambiguous
            ],
        }
        with review_path.open("w") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"Wrote {len(ambiguous)} candidates for review to {review_path}")


if __name__ == "__main__":
    main()
