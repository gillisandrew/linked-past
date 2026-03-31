"""Disambiguate 1:many DPRR→Nomisma candidates using date overlap.

For each DPRR moneyer with multiple Nomisma candidate matches, pull the
DPRR moneyer date and the CRRO coin type dates for each Nomisma person,
then pick the match with the closest date overlap.

Usage:
    uv run python scripts/disambiguate_nomisma.py
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
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


def load_existing_links() -> set[tuple[str, str]]:
    pairs = set()
    for fname in ["dprr_nomisma_confirmed.yaml", "dprr_nomisma_probable.yaml"]:
        path = LINKAGE_DIR / fname
        if path.exists():
            with path.open() as f:
                data = yaml.safe_load(f)
            for link in data.get("links", []):
                pairs.add((link["source"], link["target"]))
    return pairs


def get_dprr_moneyer_dates(store: Store) -> dict[str, list[int]]:
    """Get moneyer dates for each DPRR person. Returns {person_uri: [dates]}."""
    rows = _query_all(store, """
        PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?person ?dateStart WHERE {
          ?pa a vocab:PostAssertion ;
              vocab:isAboutPerson ?person ;
              vocab:hasOffice ?office ;
              vocab:hasDateStart ?dateStart .
          ?office rdfs:label ?officeLabel .
          FILTER(?officeLabel IN ("Office: monetalis", "Office: moneyer"))
        }
    """)
    result: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        try:
            result[r["person"]].append(int(r["dateStart"]))
        except (ValueError, TypeError):
            pass
    return dict(result)


def get_crro_issuer_dates(store: Store) -> dict[str, list[int]]:
    """Get coin type dates for each Nomisma issuer from CRRO. Returns {nomisma_uri: [dates]}."""
    rows = _query_all(store, """
        PREFIX nmo: <http://nomisma.org/ontology#>
        SELECT ?issuer ?startDate ?endDate WHERE {
          ?coin a nmo:TypeSeriesItem ;
                nmo:hasIssuer ?issuer .
          OPTIONAL { ?coin nmo:hasStartDate ?startDate }
          OPTIONAL { ?coin nmo:hasEndDate ?endDate }
        }
    """)
    result: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        uri = r["issuer"]
        for field in ["startDate", "endDate"]:
            if r.get(field):
                try:
                    result[uri].append(int(r[field]))
                except (ValueError, TypeError):
                    pass
    return dict(result)


def get_nomisma_definitions(store: Store) -> dict[str, str]:
    """Get definition text for Nomisma RRC persons."""
    rows = _query_all(store, """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?person ?def WHERE {
          ?person a foaf:Person ;
                  skos:definition ?def .
          FILTER(CONTAINS(STR(?person), "_rrc"))
        }
    """)
    return {r["person"]: r["def"] for r in rows}


def run_matching(store_dprr, store_crro, store_nomisma):
    """Re-run the matching but include ALL candidates (not just 1:1)."""
    from scripts.match_dprr_nomisma import (
        _extract_cognomen,
        _extract_nomen,
        _extract_praenomen,
        get_dprr_moneyers,
        get_nomisma_rrc_persons,
    )

    existing = load_existing_links()
    dprr_moneyers = get_dprr_moneyers(store_dprr)
    nomisma_persons = get_nomisma_rrc_persons(store_nomisma)

    # Build nomen index
    nomisma_by_nomen: dict[str, list[dict]] = {}
    for nm in nomisma_persons:
        nomen = _extract_nomen(nm["label"])
        if nomen:
            nomisma_by_nomen.setdefault(nomen.lower(), []).append(nm)

    # Deduplicate DPRR moneyers
    seen: dict[str, dict] = {}
    for m in dprr_moneyers:
        uri = m["person"]
        if uri not in seen:
            seen[uri] = m
        else:
            old = int(seen[uri].get("dateStart") or 0)
            new = int(m.get("dateStart") or 0)
            if new < old:
                seen[uri] = m

    all_candidates = []
    for dprr in seen.values():
        nomen = dprr.get("nomen", "").strip("() ").lower()
        if not nomen:
            continue
        clean_nomen = re.sub(r"[()]", "", nomen).strip()
        matches = nomisma_by_nomen.get(nomen, []) + nomisma_by_nomen.get(clean_nomen, [])
        seen_uris = set()
        for nm in matches:
            if nm["person"] in seen_uris:
                continue
            seen_uris.add(nm["person"])
            pair = (dprr["person"], nm["person"])
            if pair in existing:
                continue

            dprr_prae = _extract_praenomen(dprr["label"], is_dprr=True)
            nm_prae = _extract_praenomen(nm["label"])
            dprr_cog = (dprr.get("cognomen") or "").lower().strip("() []")
            nm_cog = _extract_cognomen(nm["label"])

            score = 0
            reasons = []

            if dprr_prae and nm_prae:
                if dprr_prae == nm_prae:
                    score += 2
                    reasons.append("praenomen")
                else:
                    if not (dprr_cog and nm_cog and dprr_cog == nm_cog):
                        continue

            score += 1
            reasons.append("nomen")

            if dprr_cog and nm_cog:
                if dprr_cog == nm_cog:
                    score += 2
                    reasons.append("cognomen")
                elif dprr_cog in nm_cog or nm_cog in dprr_cog:
                    score += 1
                    reasons.append("cognomen~")

            if score >= 4:
                all_candidates.append({
                    "dprr_uri": dprr["person"],
                    "nomisma_uri": nm["person"],
                    "dprr_label": dprr["label"],
                    "nomisma_label": nm["label"],
                    "dprr_date": dprr.get("dateStart"),
                    "score": score,
                    "reasons": "+".join(reasons),
                })

    return all_candidates


def disambiguate(
    candidates: list[dict],
    dprr_dates: dict[str, list[int]],
    crro_dates: dict[str, list[int]],
    nomisma_defs: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    """Disambiguate 1:many matches using date proximity."""
    # Group by DPRR person
    by_dprr: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        by_dprr[c["dprr_uri"]].append(c)

    confirmed = []
    unresolved = []

    for dprr_uri, group in by_dprr.items():
        if len(group) == 1:
            # Already 1:1 — but might share nomisma target with another DPRR person
            confirmed.append(group[0])
            continue

        # Get DPRR moneyer date(s)
        d_dates = dprr_dates.get(dprr_uri, [])
        if not d_dates:
            unresolved.extend(group)
            continue

        dprr_mid = sum(d_dates) / len(d_dates)

        # Score each candidate by date proximity
        scored = []
        for c in group:
            n_uri = c["nomisma_uri"]

            # Try CRRO dates first
            n_dates = crro_dates.get(n_uri, [])

            # Fall back to definition text date extraction
            if not n_dates:
                defn = nomisma_defs.get(n_uri, "")
                # Extract years like "c. 109 - 108 BC" or "71 BC"
                year_matches = re.findall(r"(\d{2,3})\s*(?:BC|B\.C\.)", defn, re.IGNORECASE)
                if not year_matches:
                    year_matches = re.findall(r"c\.\s*(\d{2,3})", defn)
                n_dates = [-int(y) for y in year_matches]

            if not n_dates:
                scored.append((c, float("inf")))
                continue

            nomisma_mid = sum(n_dates) / len(n_dates)
            distance = abs(dprr_mid - nomisma_mid)
            scored.append((c, distance))

        # Sort by distance
        scored.sort(key=lambda x: x[1])

        if not scored:
            unresolved.extend(group)
            continue

        best, best_dist = scored[0]

        if best_dist == float("inf"):
            # No dates available for any candidate
            unresolved.extend(group)
        elif len(scored) >= 2 and scored[1][1] != float("inf"):
            second_dist = scored[1][1]
            # Require clear winner: best must be at least 10 years closer than second
            if best_dist < second_dist and (second_dist - best_dist) >= 10:
                best["date_distance"] = best_dist
                best["disambiguation"] = "date_proximity"
                confirmed.append(best)
                # Rest are unresolved
                unresolved.extend(c for c, _ in scored[1:])
            else:
                unresolved.extend(c for c, _ in scored)
        else:
            # Only one candidate had dates
            best["date_distance"] = best_dist
            best["disambiguation"] = "only_dated_candidate"
            confirmed.append(best)
            unresolved.extend(c for c, _ in scored[1:])

    # Now check that confirmed targets are unique (no two DPRR persons → same Nomisma)
    target_counts = Counter(c["nomisma_uri"] for c in confirmed)
    final_confirmed = []
    for c in confirmed:
        if target_counts[c["nomisma_uri"]] == 1:
            final_confirmed.append(c)
        else:
            unresolved.append(c)

    return final_confirmed, unresolved


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    print("Opening stores...")
    dprr_store = _open_store("dprr")
    crro_store = _open_store("crro")
    nomisma_store = _open_store("nomisma")

    print("Getting DPRR moneyer dates...")
    dprr_dates = get_dprr_moneyer_dates(dprr_store)
    print(f"  {len(dprr_dates)} moneyers with dates")

    print("Getting CRRO issuer dates...")
    crro_dates = get_crro_issuer_dates(crro_store)
    print(f"  {len(crro_dates)} issuers with dates")

    print("Getting Nomisma definitions...")
    nomisma_defs = get_nomisma_definitions(nomisma_store)
    print(f"  {len(nomisma_defs)} definitions")

    print("Running name matching...")
    candidates = run_matching(dprr_store, crro_store, nomisma_store)
    print(f"  {len(candidates)} candidates (score >= 4)")

    print("Disambiguating by date...")
    confirmed, unresolved = disambiguate(candidates, dprr_dates, crro_dates, nomisma_defs)
    print(f"  {len(confirmed)} date-disambiguated matches")
    print(f"  {len(unresolved)} still unresolved")

    # Print confirmed
    print("\n" + "=" * 130)
    print(f"{'Dist':>5}  {'Method':<22}  {'DPRR Date':>9}  {'DPRR Label':<45}  {'Nomisma Label':<40}")
    print("-" * 130)
    for c in sorted(confirmed, key=lambda x: x.get("dprr_date") or ""):
        dist = c.get("date_distance", "?")
        if isinstance(dist, float):
            dist = f"{dist:.0f}yr"
        method = c.get("disambiguation", "1:1")
        label = c['dprr_label'][:45]
        nom_label = c['nomisma_label'][:40]
        print(f"{str(dist):>5}  {method:<22}  {c.get('dprr_date', '?'):>9}  {label:<45}  {nom_label:<40}")

    # Merge into confirmed YAML
    if confirmed:
        conf_path = LINKAGE_DIR / "dprr_nomisma_confirmed.yaml"
        with conf_path.open() as f:
            conf_data = yaml.safe_load(f)

        existing_pairs = {(link["source"], link["target"]) for link in conf_data["links"]}
        added = 0
        for c in confirmed:
            pair = (c["dprr_uri"], c["nomisma_uri"])
            if pair not in existing_pairs:
                method = c.get("disambiguation", "1:1")
                dist = c.get("date_distance", "?")
                dist_str = f"{dist:.0f}yr" if isinstance(dist, float) else str(dist)
                conf_data["links"].append({
                    "source": c["dprr_uri"],
                    "target": c["nomisma_uri"],
                    "note": (
                        f"DPRR: {c['dprr_label'][:60]}; Nomisma: {c['nomisma_label']}; "
                        f"disambiguated by {method} ({dist_str})"
                    ),
                })
                added += 1

        with conf_path.open("w") as f:
            yaml.dump(conf_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        print(f"\nAdded {added} new links to {conf_path}")
        print(f"Total confirmed links: {len(conf_data['links'])}")

    if unresolved:
        print(f"\n{len(unresolved)} unresolved candidates remain for manual review")


if __name__ == "__main__":
    main()
