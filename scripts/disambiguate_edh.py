"""Disambiguate 1:many DPRR→EDH candidates using date overlap.

For each ambiguous match, compare DPRR person's era (eraFrom/eraTo) and
office dates against EDH inscription dates (hasStartDate/hasEndDate).
Pick the match with best date overlap.

Usage:
    uv run python scripts/disambiguate_edh.py
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
    "ap.": "appius", "ap": "appius",
}


def _parse_roman_name(name: str) -> dict:
    """Parse a Roman name string into components."""
    clean = re.sub(r"[?\[\]]", "", name).strip()
    parts = clean.split()
    if not parts:
        return {}
    result = {}
    first_lower = parts[0].lower().rstrip(".")
    first_with_dot = parts[0].lower()
    prae = _PRAENOMEN_MAP.get(first_with_dot) or _PRAENOMEN_MAP.get(first_lower)
    if prae:
        result["praenomen"] = prae
        parts = parts[1:]
    if not parts:
        return result
    result["nomen"] = parts[0].rstrip(".,;")
    cognomina = []
    for p in parts[1:]:
        p_clean = p.rstrip(".,;")
        if p_clean.lower() in ("f", "n", "fil", "filius", "nepos"):
            continue
        if len(p_clean) <= 2 and p_clean[0].isupper():
            continue
        if p_clean and p_clean[0].isupper():
            cognomina.append(p_clean)
    if cognomina:
        result["cognomen"] = cognomina[0]
    return result


def get_dprr_persons(store: Store) -> dict[str, dict]:
    """Get all DPRR persons with structured names and era dates."""
    rows = _query_all(store, """
        PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?person ?label ?nomen ?cognomen ?praenomenLabel
               ?eraFrom ?eraTo WHERE {
          ?person a vocab:Person ;
                  rdfs:label ?label ;
                  vocab:hasNomen ?nomen .
          OPTIONAL { ?person vocab:hasCognomen ?cognomen }
          OPTIONAL { ?person vocab:hasPraenomen ?prae . ?prae rdfs:label ?praenomenLabel }
          OPTIONAL { ?person vocab:hasEraFrom ?eraFrom }
          OPTIONAL { ?person vocab:hasEraTo ?eraTo }
        }
    """)
    by_uri = {}
    for r in rows:
        uri = r["person"]
        if uri not in by_uri:
            by_uri[uri] = r
    return by_uri


def get_edh_elite_persons(store: Store) -> dict[str, dict]:
    """Get EDH senatorial/equestrian persons, then fetch inscription dates separately."""
    # Step 1: Get persons with names and attestation URIs
    print("    Step 1: querying persons...")
    person_rows = _query_all(store, """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?person ?name ?att WHERE {
          ?person a <http://lawd.info/ontology/Person> ;
                  foaf:name ?name .
          FILTER EXISTS {
            ?person foaf:member ?s .
            FILTER(?s IN (
              <https://edh-www.adw.uni-heidelberg.de/edh/social_status/senatorial_order>,
              <https://edh-www.adw.uni-heidelberg.de/edh/social_status/equestrian_order>
            ))
          }
          OPTIONAL { ?person <http://lawd.info/ontology/hasAttestation> ?att }
        }
    """)
    print(f"    Step 1 done: {len(person_rows)} rows")

    # Build person dict and collect inscription URIs
    by_uri: dict[str, dict] = {}
    inscription_uris: dict[str, set[str]] = defaultdict(set)  # person → inscription URIs
    for r in person_rows:
        uri = r["person"]
        if uri not in by_uri:
            by_uri[uri] = {"person": uri, "name": r["name"]}
        if r.get("att"):
            # Extract inscription URI from attestation URI
            # Format: .../inschrift/HD012345/1#ref → .../inschrift/HD012345
            att = r["att"]
            parts = att.split("/")
            # Find the "inschrift" segment and take the next part (HD number)
            for i, p in enumerate(parts):
                if p == "inschrift" and i + 1 < len(parts):
                    hd = parts[i + 1].split("#")[0]
                    insc_uri = "/".join(parts[:i+1]) + "/" + hd
                    inscription_uris[uri].add(insc_uri)
                    break

    # Step 2: Get inscription dates in bulk
    print("    Step 2: querying inscription dates...")
    date_rows = _query_all(store, """
        PREFIX nmo: <http://nomisma.org/ontology#>
        PREFIX epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#>
        SELECT ?insc ?startDate ?endDate WHERE {
          ?insc a epi:Inscription .
          OPTIONAL { ?insc nmo:hasStartDate ?startDate }
          OPTIONAL { ?insc nmo:hasEndDate ?endDate }
          FILTER(BOUND(?startDate) || BOUND(?endDate))
        }
    """)
    print(f"    Step 2 done: {len(date_rows)} inscriptions with dates")

    insc_dates: dict[str, tuple] = {}
    for r in date_rows:
        insc_dates[r["insc"]] = (r.get("startDate"), r.get("endDate"))

    # Merge dates into persons
    for person_uri, insc_set in inscription_uris.items():
        if person_uri not in by_uri:
            continue
        for insc_uri in insc_set:
            dates = insc_dates.get(insc_uri)
            if dates:
                start, end = dates
                if start and not by_uri[person_uri].get("inscStart"):
                    by_uri[person_uri]["inscStart"] = start
                if end and not by_uri[person_uri].get("inscEnd"):
                    by_uri[person_uri]["inscEnd"] = end

    return by_uri


def match_all_candidates(
    dprr_persons: dict[str, dict],
    edh_persons: dict[str, dict],
    existing_pairs: set[tuple[str, str]],
) -> list[dict]:
    """Match all DPRR→EDH candidates by name (score >= 5)."""
    # Build nomen index for DPRR
    dprr_by_nomen: dict[str, list[dict]] = {}
    for d in dprr_persons.values():
        nomen = d.get("nomen", "").strip("() ").lower()
        nomen = re.sub(r"[()]", "", nomen).strip()
        if nomen and len(nomen) > 2:
            dprr_by_nomen.setdefault(nomen, []).append(d)

    candidates = []
    for edh in edh_persons.values():
        name = edh.get("name", "")
        if not name or len(name) < 5:
            continue
        parsed = _parse_roman_name(name)
        edh_nomen = (parsed.get("nomen") or "").lower()
        edh_cog = (parsed.get("cognomen") or "").lower()
        edh_prae = parsed.get("praenomen")
        if not edh_nomen or len(edh_nomen) < 3:
            continue

        dprr_matches = dprr_by_nomen.get(edh_nomen, [])
        if edh_nomen.endswith("ia"):
            dprr_matches = dprr_matches + dprr_by_nomen.get(edh_nomen[:-1] + "us", [])

        for dprr in dprr_matches:
            pair = (dprr["person"], edh["person"])
            if pair in existing_pairs:
                continue

            dprr_cog = (dprr.get("cognomen") or "").lower().strip("() []")
            dprr_prae_label = (dprr.get("praenomenLabel") or "").lower()
            dprr_prae = _PRAENOMEN_MAP.get(dprr_prae_label.split(":")[-1].strip().lower().rstrip("."))

            score = 0
            reasons = []
            score += 1
            reasons.append("nomen")

            if edh_prae and dprr_prae:
                if edh_prae == dprr_prae:
                    score += 2
                    reasons.append("praenomen")
                else:
                    continue
            if edh_cog and dprr_cog:
                if edh_cog == dprr_cog:
                    score += 2
                    reasons.append("cognomen")
                elif edh_cog in dprr_cog or dprr_cog in edh_cog:
                    score += 1
                    reasons.append("cognomen~")
                else:
                    continue

            if score >= 5:
                candidates.append({
                    "dprr_uri": dprr["person"],
                    "edh_uri": edh["person"],
                    "dprr_label": dprr["label"],
                    "edh_name": name,
                    "dprr_eraFrom": dprr.get("eraFrom"),
                    "dprr_eraTo": dprr.get("eraTo"),
                    "edh_inscStart": edh.get("inscStart"),
                    "edh_inscEnd": edh.get("inscEnd"),
                    "score": score,
                    "reasons": "+".join(reasons),
                })

    return candidates


def _era_overlaps(dprr_from, dprr_to, edh_start, edh_end) -> float | None:
    """Check if DPRR era overlaps with EDH inscription date range.
    Returns overlap score (lower = better) or None if no dates."""
    try:
        d_from = int(dprr_from) if dprr_from else None
        d_to = int(dprr_to) if dprr_to else None
        e_start = int(edh_start) if edh_start else None
        e_end = int(edh_end) if edh_end else None
    except (ValueError, TypeError):
        return None

    if d_from is None and d_to is None:
        return None
    if e_start is None and e_end is None:
        return None

    # Use midpoint of inscription date range
    if e_start is not None and e_end is not None:
        e_mid = (e_start + e_end) / 2
    elif e_start is not None:
        e_mid = e_start
    else:
        e_mid = e_end

    # Check if inscription date falls within DPRR era
    if d_from is not None and d_to is not None:
        if d_from <= e_mid <= d_to:
            return 0.0  # Perfect overlap
        else:
            return min(abs(e_mid - d_from), abs(e_mid - d_to))
    elif d_from is not None:
        return abs(e_mid - d_from)
    else:
        return abs(e_mid - d_to)


def disambiguate(candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    """Disambiguate using date overlap and 1:1 filtering."""
    # Group by DPRR person
    by_dprr: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        by_dprr[c["dprr_uri"]].append(c)

    date_resolved = []
    still_ambiguous = []

    for dprr_uri, group in by_dprr.items():
        if len(group) == 1:
            date_resolved.append(group[0])
            continue

        # Score each by date overlap
        scored = []
        for c in group:
            dist = _era_overlaps(
                c["dprr_eraFrom"], c["dprr_eraTo"],
                c["edh_inscStart"], c["edh_inscEnd"],
            )
            scored.append((c, dist))

        # Separate dated from undated
        dated = [(c, d) for c, d in scored if d is not None]
        undated = [(c, d) for c, d in scored if d is None]

        if not dated:
            still_ambiguous.extend(c for c, _ in scored)
            continue

        dated.sort(key=lambda x: x[1])
        best, best_dist = dated[0]

        if len(dated) >= 2:
            second_dist = dated[1][1]
            if best_dist <= 30 and (second_dist - best_dist) >= 20:
                best["date_distance"] = best_dist
                best["disambiguation"] = "date_overlap"
                date_resolved.append(best)
                still_ambiguous.extend(c for c, _ in dated[1:])
                still_ambiguous.extend(c for c, _ in undated)
            else:
                still_ambiguous.extend(c for c, _ in scored)
        else:
            if best_dist <= 50:
                best["date_distance"] = best_dist
                best["disambiguation"] = "only_dated"
                date_resolved.append(best)
                still_ambiguous.extend(c for c, _ in undated)
            else:
                still_ambiguous.extend(c for c, _ in scored)

    # Final pass: ensure targets are unique
    target_counts = Counter(c["edh_uri"] for c in date_resolved)
    confirmed = []
    for c in date_resolved:
        if target_counts[c["edh_uri"]] == 1:
            confirmed.append(c)
        else:
            still_ambiguous.append(c)

    return confirmed, still_ambiguous


def main():
    print("Opening stores...")
    dprr_store = _open_store("dprr")
    edh_store = _open_store("edh")

    print("Loading DPRR persons...")
    dprr_persons = get_dprr_persons(dprr_store)
    print(f"  {len(dprr_persons)} persons")

    print("Loading EDH elite persons with inscription dates...")
    edh_persons = get_edh_elite_persons(edh_store)
    print(f"  {len(edh_persons)} persons")

    # Load existing confirmed links
    conf_path = LINKAGE_DIR / "dprr_edh_confirmed.yaml"
    existing_pairs: set[tuple[str, str]] = set()
    if conf_path.exists():
        with conf_path.open() as f:
            conf_data = yaml.safe_load(f)
        for link in conf_data.get("links", []):
            existing_pairs.add((link["source"], link["target"]))
        print(f"  {len(existing_pairs)} existing confirmed links")

    print("Matching all candidates...")
    candidates = match_all_candidates(dprr_persons, edh_persons, existing_pairs)
    print(f"  {len(candidates)} name matches (score >= 5)")

    # How many are already 1:1?
    dprr_counts = Counter(c["dprr_uri"] for c in candidates)
    edh_counts = Counter(c["edh_uri"] for c in candidates)
    already_unique = [c for c in candidates
                      if dprr_counts[c["dprr_uri"]] == 1 and edh_counts[c["edh_uri"]] == 1]
    ambiguous = [c for c in candidates if c not in already_unique]
    print(f"  {len(already_unique)} already 1:1 (new since last run)")
    print(f"  {len(ambiguous)} ambiguous")

    print("Disambiguating by date...")
    date_confirmed, unresolved = disambiguate(ambiguous)
    print(f"  {len(date_confirmed)} date-disambiguated")
    print(f"  {len(unresolved)} still unresolved")

    all_new = already_unique + date_confirmed

    # Print results
    print(f"\n{'=' * 130}")
    print(f"{'Score':>5}  {'Method':<15}  {'Dist':>6}  {'DPRR Label':<45}  {'EDH Name':<35}")
    print(f"{'-' * 130}")
    for c in sorted(all_new, key=lambda x: x["dprr_label"]):
        method = c.get("disambiguation", "1:1")
        dist = c.get("date_distance")
        dist_str = f"{dist:.0f}yr" if isinstance(dist, (int, float)) else ""
        print(f"{c['score']:>5}  {method:<15}  {dist_str:>6}  {c['dprr_label'][:45]:<45}  {c['edh_name'][:35]:<35}")

    # Merge into confirmed
    if all_new:
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
                        "Praenomen + nomen + cognomen matching between "
                        "DPRR persons and EDH senatorial/equestrian persons"
                    ),
                    "author": "linked-past project",
                    "date": "2026-03-30",
                },
                "links": [],
            }

        existing_in_file = {(link["source"], link["target"]) for link in conf_data["links"]}
        added = 0
        for c in all_new:
            pair = (c["dprr_uri"], c["edh_uri"])
            if pair not in existing_in_file:
                method = c.get("disambiguation", "1:1")
                dist = c.get("date_distance")
                note = f"DPRR: {c['dprr_label'][:60]}; EDH: {c['edh_name']}"
                if method != "1:1":
                    dist_str = f"{dist:.0f}yr" if isinstance(dist, (int, float)) else "?"
                    note += f"; disambiguated by {method} ({dist_str})"
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

    print(f"\n{len(unresolved)} unresolved candidates remain")


if __name__ == "__main__":
    main()
