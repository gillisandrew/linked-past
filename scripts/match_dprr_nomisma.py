"""Match DPRR moneyers to Nomisma RRC persons by name and date.

Reads both datasets from local Oxigraph stores, cross-references by
abbreviated name forms, and outputs candidate matches as YAML for review.

Usage:
    uv run python scripts/match_dprr_nomisma.py
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml
from pyoxigraph import Store

DATA_DIR = Path.home() / ".local" / "share" / "linked-past"
LINKAGE_DIR = Path(__file__).resolve().parents[1] / "packages" / "linked-past" / "linked_past" / "linkages"


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


def _normalize(s: str) -> str:
    """Normalize a Roman name for fuzzy matching."""
    s = unicodedata.normalize("NFKD", s)
    s = s.lower().strip()
    # Remove RE numbers, parentheses, question marks, brackets
    s = re.sub(r"\([\d,.\s]*\)", "", s)
    s = re.sub(r"[\[\]?()]", "", s)
    # Normalize praenomen abbreviations
    for abbr, full in [
        ("c.", "gaius"), ("cn.", "gnaeus"), ("l.", "lucius"),
        ("m.", "marcus"), ("m'.", "manius"), ("mn.", "manius"),
        ("p.", "publius"), ("q.", "quintus"), ("sex.", "sextus"),
        ("ser.", "servius"), ("sp.", "spurius"), ("t.", "titus"),
        ("ti.", "tiberius"), ("a.", "aulus"), ("d.", "decimus"),
        ("n.", "numerius"), ("ap.", "appius"),
    ]:
        s = re.sub(rf"\b{re.escape(abbr)}\b", full, s)
    # Remove filiation patterns like "m. f. m. n." or "c. f. c. n."
    s = re.sub(r"\b\w+\.\s*f\.\s*\w+\.\s*n\.\s*", "", s)
    s = re.sub(r"\b\w+\.\s*f\.\s*", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_nomen(label: str) -> str | None:
    """Extract the nomen (family name) from a Nomisma label like 'C. Vibius Pansa'."""
    parts = label.strip().split()
    if len(parts) < 2:
        return None
    # Skip praenomen (first element if it looks like an abbreviation)
    start = 0
    if parts[0].endswith(".") or parts[0] in ("Mn", "Ti"):
        start = 1
    if start < len(parts):
        return parts[start].rstrip(".,;")
    return None


def load_existing_links() -> set[tuple[str, str]]:
    """Load already-confirmed source→target pairs."""
    pairs = set()
    for fname in ["dprr_nomisma_confirmed.yaml", "dprr_nomisma_probable.yaml"]:
        path = LINKAGE_DIR / fname
        if path.exists():
            with path.open() as f:
                data = yaml.safe_load(f)
            for link in data.get("links", []):
                pairs.add((link["source"], link["target"]))
    return pairs


def get_dprr_moneyers(store: Store) -> list[dict]:
    return _query_all(store, """
        PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?person ?label ?nomen ?cognomen ?dateStart WHERE {
          ?pa a vocab:PostAssertion ;
              vocab:isAboutPerson ?person ;
              vocab:hasOffice ?office ;
              vocab:hasDateStart ?dateStart .
          ?office rdfs:label ?officeLabel .
          FILTER(?officeLabel IN ("Office: monetalis", "Office: moneyer"))
          ?person rdfs:label ?label ;
                  vocab:hasNomen ?nomen .
          OPTIONAL { ?person vocab:hasCognomen ?cognomen }
        }
        ORDER BY ?dateStart
    """)


def get_nomisma_rrc_persons(store: Store) -> list[dict]:
    return _query_all(store, """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT DISTINCT ?person ?label WHERE {
          ?person a foaf:Person ;
                  skos:prefLabel ?label ;
                  skos:inScheme <http://nomisma.org/id/> .
          FILTER(LANG(?label) = "en")
          FILTER(CONTAINS(STR(?person), "_rrc"))
          FILTER NOT EXISTS { ?person owl:deprecated "true"^^xsd:boolean }
        }
    """)


_PRAENOMEN_MAP = {
    "c.": "gaius", "cn.": "gnaeus", "l.": "lucius",
    "m.": "marcus", "m'.": "manius", "mn.": "manius", "mn": "manius",
    "p.": "publius", "q.": "quintus", "sex.": "sextus",
    "ser.": "servius", "sp.": "spurius", "t.": "titus",
    "ti.": "tiberius", "ti": "tiberius", "a.": "aulus",
    "d.": "decimus", "n.": "numerius", "ap.": "appius",
}


def _extract_praenomen(label: str, is_dprr: bool = False) -> str | None:
    """Extract normalized praenomen from a name label."""
    parts = label.strip().split()
    if not parts:
        return None
    # DPRR labels start with "CODE1234 Praen. Nomen..."
    idx = 1 if is_dprr and len(parts) > 1 else 0
    token = parts[idx].lower()
    return _PRAENOMEN_MAP.get(token, None)


def match_candidates(
    dprr_moneyers: list[dict],
    nomisma_persons: list[dict],
    existing: set[tuple[str, str]],
) -> list[dict]:
    """Find candidate matches by praenomen + nomen + cognomen."""
    # Build nomen→nomisma index
    nomisma_by_nomen: dict[str, list[dict]] = {}
    for nm in nomisma_persons:
        nomen = _extract_nomen(nm["label"])
        if nomen:
            nomisma_by_nomen.setdefault(nomen.lower(), []).append(nm)

    # Deduplicate DPRR moneyers by person URI, keep earliest date
    seen_persons: dict[str, dict] = {}
    for m in dprr_moneyers:
        uri = m["person"]
        if uri not in seen_persons:
            seen_persons[uri] = m
        else:
            existing_date = int(seen_persons[uri].get("dateStart") or 0)
            new_date = int(m.get("dateStart") or 0)
            if new_date < existing_date:
                seen_persons[uri] = m

    candidates = []
    for dprr in seen_persons.values():
        nomen = dprr.get("nomen", "").strip("() ").lower()
        if not nomen:
            continue

        # Look up by nomen
        clean_nomen = re.sub(r"[()]", "", nomen).strip()
        nomisma_matches = nomisma_by_nomen.get(nomen, []) + nomisma_by_nomen.get(clean_nomen, [])
        # Deduplicate
        seen_uris = set()
        unique_matches = []
        for nm in nomisma_matches:
            if nm["person"] not in seen_uris:
                seen_uris.add(nm["person"])
                unique_matches.append(nm)

        for nm in unique_matches:
            pair = (dprr["person"], nm["person"])
            if pair in existing:
                continue

            # Extract praenomina
            dprr_prae = _extract_praenomen(dprr["label"], is_dprr=True)
            nm_prae = _extract_praenomen(nm["label"])

            # Check cognomen overlap
            dprr_cog = (dprr.get("cognomen") or "").lower().strip("() []")
            nm_cog = _extract_cognomen(nm["label"])

            score = 0
            reasons = []

            # Praenomen match
            if dprr_prae and nm_prae and dprr_prae == nm_prae:
                score += 2
                reasons.append("praenomen")
            elif dprr_prae and nm_prae and dprr_prae != nm_prae:
                # Praenomen mismatch — skip unless cognomen is very distinctive
                if not (dprr_cog and nm_cog and dprr_cog == nm_cog):
                    continue

            # Nomen match (already guaranteed by lookup)
            score += 1
            reasons.append("nomen")

            # Cognomen match
            if dprr_cog and nm_cog and dprr_cog == nm_cog:
                score += 2
                reasons.append("cognomen")
            elif dprr_cog and nm_cog and (dprr_cog in nm_cog or nm_cog in dprr_cog):
                score += 1
                reasons.append("cognomen~")

            if score >= 4:
                candidates.append({
                    "source": dprr["person"],
                    "target": nm["person"],
                    "dprr_label": dprr["label"],
                    "nomisma_label": nm["label"],
                    "dprr_date": dprr.get("dateStart"),
                    "score": score,
                    "reasons": "+".join(reasons),
                })

    # Sort by score descending, then by date
    candidates.sort(key=lambda c: (-c["score"], c.get("dprr_date") or ""))
    return candidates


def _extract_cognomen(label: str) -> str | None:
    """Extract likely cognomen from a Nomisma label."""
    parts = label.strip().split()
    if len(parts) >= 3:
        # Skip praenomen and nomen
        start = 0
        if parts[0].endswith(".") or parts[0] in ("Mn", "Ti"):
            start = 1
        if start + 1 < len(parts):
            return parts[start + 1].lower().rstrip(".,;")
    return None


def main():
    print("Opening stores...")
    dprr_store = _open_store("dprr")
    nomisma_store = _open_store("nomisma")

    print("Loading existing links...")
    existing = load_existing_links()
    print(f"  {len(existing)} existing links")

    print("Querying DPRR moneyers...")
    dprr_moneyers = get_dprr_moneyers(dprr_store)
    print(f"  {len(dprr_moneyers)} moneyer post assertions")

    print("Querying Nomisma RRC persons...")
    nomisma_persons = get_nomisma_rrc_persons(nomisma_store)
    print(f"  {len(nomisma_persons)} RRC persons")

    print("Matching candidates...")
    candidates = match_candidates(dprr_moneyers, nomisma_persons, existing)
    print(f"  {len(candidates)} new candidate matches (score >= 2)\n")

    # Output as review table
    print("=" * 100)
    print(f"{'Score':>5}  {'DPRR Date':>10}  {'DPRR Label':<45}  {'Nomisma Label':<40}")
    print("-" * 100)
    for c in candidates:
        label = c['dprr_label'][:45]
        nom_label = c['nomisma_label'][:40]
        print(f"{c['score']:>5}  {c['dprr_date'] or '?':>10}  {label:<45}  {nom_label:<40}  {c['reasons']}")

    # Output YAML for confirmed matches (score >= 2)
    output_path = LINKAGE_DIR / "dprr_nomisma_candidates.yaml"
    yaml_data = {
        "metadata": {
            "source_dataset": "dprr",
            "target_dataset": "nomisma",
            "relationship": "skos:closeMatch",
            "confidence": "candidate",
            "method": "automated_name_matching",
            "basis": "Nomen + cognomen matching between DPRR moneyer records and Nomisma RRC person authorities",
            "author": "linked-past project",
            "date": "2026-03-30",
        },
        "links": [
            {
                "source": c["source"],
                "target": c["target"],
                "note": (
                    f"DPRR: {c['dprr_label'][:60]} ({c['dprr_date'] or '?'} BC); "
                    f"Nomisma: {c['nomisma_label']}; score={c['score']}"
                ),
            }
            for c in candidates
        ],
    }
    with output_path.open("w") as f:
        yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\nWrote {len(candidates)} candidates to {output_path}")


if __name__ == "__main__":
    main()
