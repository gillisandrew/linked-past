"""Match DPRR persons to EDH inscription persons by name.

Focuses on EDH persons of senatorial or equestrian order, matching
against DPRR persons by nomen + cognomen + praenomen agreement.

Usage:
    uv run python scripts/match_dprr_edh.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml
from pyoxigraph import Store

DATA_DIR = Path.home() / ".local" / "share" / "linked-past"
LINKAGE_DIR = Path(__file__).resolve().parents[1] / "packages" / "linked-past" / "linked_past" / "linkages"

_PRAENOMEN_MAP = {
    "c.": "gaius", "c": "gaius",
    "cn.": "gnaeus", "cn": "gnaeus",
    "l.": "lucius", "l": "lucius",
    "m.": "marcus", "m": "marcus",
    "m'.": "manius", "mn.": "manius", "mn": "manius",
    "p.": "publius", "p": "publius",
    "q.": "quintus", "q": "quintus",
    "sex.": "sextus", "sex": "sextus",
    "ser.": "servius", "ser": "servius",
    "sp.": "spurius", "sp": "spurius",
    "t.": "titus", "t": "titus",
    "ti.": "tiberius", "ti": "tiberius",
    "a.": "aulus", "a": "aulus",
    "d.": "decimus", "d": "decimus",
    "n.": "numerius",
    "ap.": "appius", "ap": "appius",
    # Greek equivalents
    "γ.": "gaius", "γάιος": "gaius", "γαίου": "gaius",
    "γν.": "gnaeus", "γναῖος": "gnaeus",
    "λ.": "lucius", "λεύκιος": "lucius", "λευκίου": "lucius",
    "μ.": "marcus", "μάρκος": "marcus", "μάρκου": "marcus",
    "μάνιος": "manius", "μανίου": "manius",
    "π.": "publius", "πόπλιος": "publius",
    "κ.": "quintus", "κόιντος": "quintus",
    "τ.": "titus", "τίτος": "titus",
    "σέξτος": "sextus",
    "τιβέριος": "tiberius",
}


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


def _parse_roman_name(name: str) -> dict:
    """Parse a Roman name string into praenomen, nomen, cognomen components."""
    # Remove question marks, brackets
    clean = re.sub(r"[?\[\]]", "", name).strip()
    parts = clean.split()
    if not parts:
        return {}

    result = {}

    # Try to identify praenomen
    first_lower = parts[0].lower().rstrip(".")
    first_with_dot = parts[0].lower()
    prae = _PRAENOMEN_MAP.get(first_with_dot) or _PRAENOMEN_MAP.get(first_lower)
    if prae:
        result["praenomen"] = prae
        parts = parts[1:]

    if not parts:
        return result

    # Next part is typically nomen (gens name, ending in -ius/-ia)
    result["nomen"] = parts[0].rstrip(".,;")

    # Remaining parts are cognomen(s), skip filiation like "f.", "n."
    cognomina = []
    skip_next = False
    for i, p in enumerate(parts[1:], 1):
        p_clean = p.rstrip(".,;")
        if skip_next:
            skip_next = False
            continue
        if p_clean.lower() in ("f", "n", "fil", "filius", "nepos"):
            continue
        if len(p_clean) <= 2 and p_clean[0].isupper():
            # Likely abbreviation like tribe or filiation
            skip_next = True
            continue
        if p_clean and p_clean[0].isupper():
            cognomina.append(p_clean)

    if cognomina:
        result["cognomen"] = cognomina[0]
        if len(cognomina) > 1:
            result["cognomina_extra"] = cognomina[1:]

    return result


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
    for edh in edh_persons:
        name = edh.get("name", "")
        if not name or len(name) < 5:
            continue

        parsed = _parse_roman_name(name)
        edh_nomen = (parsed.get("nomen") or "").lower()
        edh_cog = (parsed.get("cognomen") or "").lower()
        edh_prae = parsed.get("praenomen")

        if not edh_nomen or len(edh_nomen) < 3:
            continue

        # Look for DPRR matches by nomen
        # Try exact nomen match
        dprr_matches = dprr_by_nomen.get(edh_nomen, [])
        # Also try -ius → -ia variation (for women)
        if edh_nomen.endswith("ia"):
            masc = edh_nomen[:-1] + "us"
            dprr_matches = dprr_matches + dprr_by_nomen.get(masc, [])

        for dprr in dprr_matches:
            dprr_nomen = re.sub(r"[()]", "", dprr.get("nomen", "")).strip().lower()
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
                candidates.append({
                    "dprr_uri": dprr["person"],
                    "edh_uri": edh["person"],
                    "dprr_label": dprr["label"],
                    "edh_name": name,
                    "edh_inscription": edh.get("inscription"),
                    "dprr_era": f"{dprr.get('eraFrom', '?')} to {dprr.get('eraTo', '?')}",
                    "dprr_office": dprr.get("highestOffice", ""),
                    "score": score,
                    "reasons": "+".join(reasons),
                })

    # Sort by score descending
    candidates.sort(key=lambda c: (-c["score"], c["dprr_label"]))
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

    print("Matching candidates...")
    candidates = match_candidates(dprr_persons, edh_persons)
    print(f"  {len(candidates)} raw matches (score >= 5)")

    # Filter to safe 1:1 matches
    dprr_counts = Counter(c["dprr_uri"] for c in candidates)
    edh_counts = Counter(c["edh_uri"] for c in candidates)
    safe = [c for c in candidates if dprr_counts[c["dprr_uri"]] == 1 and edh_counts[c["edh_uri"]] == 1]
    ambiguous = [c for c in candidates if c not in safe]

    print(f"  {len(safe)} safe 1:1 matches")
    print(f"  {len(ambiguous)} ambiguous (1:many or many:1)")

    # Print safe matches
    print("\n" + "=" * 120)
    print(f"{'Score':>5}  {'DPRR Label':<50}  {'EDH Name':<35}  {'DPRR Office':<20}")
    print("-" * 120)
    for c in safe:
        print(f"{c['score']:>5}  {c['dprr_label'][:50]:<50}  {c['edh_name'][:35]:<35}  {c['dprr_office'][:20]}")

    # Write safe matches as YAML
    if safe:
        output_path = LINKAGE_DIR / "dprr_edh_confirmed.yaml"
        yaml_data = {
            "metadata": {
                "source_dataset": "dprr",
                "target_dataset": "edh",
                "relationship": "skos:closeMatch",
                "confidence": "confirmed",
                "method": "automated_name_matching",
                "basis": "Praenomen + nomen + cognomen matching between DPRR persons and EDH senatorial/equestrian persons",
                "author": "linked-past project",
                "date": "2026-03-30",
            },
            "links": [
                {
                    "source": c["dprr_uri"],
                    "target": c["edh_uri"],
                    "note": f"DPRR: {c['dprr_label'][:60]}; EDH: {c['edh_name']}; {c['dprr_office']}",
                }
                for c in safe
            ],
        }
        with output_path.open("w") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"\nWrote {len(safe)} confirmed links to {output_path}")

    # Write ambiguous for review
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
