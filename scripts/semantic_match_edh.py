"""Find DPRR↔EDH matches using embedding-based semantic similarity.

Uses FastEmbed (BAAI/bge-small-en-v1.5) to embed rich DPRR person
descriptions and EDH person names, then finds high-similarity pairs
that name-based matching missed.

Catches: Greek transliterations, spelling variants, abbreviated names,
different cognomen forms, and names where nomen matching fails due to
orthographic differences (Publicius/Poblicius, Vettius/Vettii).

Usage:
    uv run python scripts/semantic_match_edh.py
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import numpy as np
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


def get_dprr_person_descriptions(store: Store) -> list[dict]:
    """Build rich text descriptions for DPRR persons."""
    # Get persons with names
    persons = _query_all(store, """
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

    by_uri = {}
    for r in persons:
        uri = r["person"]
        if uri not in by_uri:
            by_uri[uri] = r

    # Get office holdings for richer descriptions
    offices = _query_all(store, """
        PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?person ?officeName ?dateStart WHERE {
          ?pa a vocab:PostAssertion ;
              vocab:isAboutPerson ?person ;
              vocab:hasOffice ?office ;
              vocab:hasDateStart ?dateStart .
          ?office rdfs:label ?officeName .
        }
    """)

    offices_by_person: dict[str, list[str]] = defaultdict(list)
    for r in offices:
        uri = r["person"]
        date = r.get("dateStart", "?")
        offices_by_person[uri].append(f"{r['officeName']} {date}")

    # Build descriptions
    result = []
    for uri, p in by_uri.items():
        # Build a rich text description
        parts = []

        # Full name from label (strip DPRR ID prefix)
        label = p["label"]
        # Remove "CODE1234 " prefix
        clean_name = re.sub(r"^[A-Z]{4}\d+ ", "", label)
        parts.append(clean_name)

        # Praenomen expansion
        prae = (p.get("praenomenLabel") or "").replace("Praenomen: ", "")
        nomen = p.get("nomen", "")
        cognomen = p.get("cognomen", "")
        if prae and nomen:
            parts.append(f"{prae} {nomen}" + (f" {cognomen}" if cognomen else ""))

        # Era
        era_from = p.get("eraFrom")
        era_to = p.get("eraTo")
        if era_from:
            from_bc = f"{abs(int(era_from))} BC" if int(era_from) < 0 else f"{era_from} AD"
            to_bc = f"{abs(int(era_to))} BC" if era_to and int(era_to) < 0 else (f"{era_to} AD" if era_to else "?")
            parts.append(f"{from_bc} to {to_bc}")

        # Highest office
        if p.get("highestOffice"):
            parts.append(p["highestOffice"])

        # Key offices (up to 5)
        person_offices = offices_by_person.get(uri, [])
        if person_offices:
            parts.extend(person_offices[:5])

        description = ". ".join(parts)
        result.append({
            "uri": uri,
            "label": label,
            "nomen": nomen,
            "cognomen": cognomen,
            "description": description,
        })

    return result


def get_edh_elite_persons(store: Store) -> list[dict]:
    """Get EDH senatorial/equestrian persons."""
    rows = _query_all(store, """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?person ?name WHERE {
          ?person a <http://lawd.info/ontology/Person> ;
                  foaf:name ?name .
          FILTER EXISTS {
            ?person foaf:member ?s .
            FILTER(?s IN (
              <https://edh-www.adw.uni-heidelberg.de/edh/social_status/senatorial_order>,
              <https://edh-www.adw.uni-heidelberg.de/edh/social_status/equestrian_order>
            ))
          }
        }
    """)
    by_uri = {}
    for r in rows:
        if r["person"] not in by_uri:
            by_uri[r["person"]] = r
    return list(by_uri.values())


def load_existing_links() -> set[tuple[str, str]]:
    """Load all existing DPRR→EDH confirmed pairs."""
    pairs = set()
    path = LINKAGE_DIR / "dprr_edh_confirmed.yaml"
    if path.exists():
        with path.open() as f:
            data = yaml.safe_load(f)
        for link in data.get("links", []):
            pairs.add((link["source"], link["target"]))
    return pairs


def load_name_match_pairs() -> set[tuple[str, str]]:
    """Load all pairs that name-based matching already found (confirmed + ambiguous)."""
    # Re-run the name matcher to get ALL pairs it considered
    # For efficiency, we'll just load existing + compute on the fly
    return load_existing_links()


def main():
    from fastembed import TextEmbedding

    print("Loading FastEmbed model...")
    model = TextEmbedding("BAAI/bge-small-en-v1.5")

    print("Opening stores...")
    dprr_store = _open_store("dprr")
    edh_store = _open_store("edh")

    print("Building DPRR person descriptions...")
    dprr_persons = get_dprr_person_descriptions(dprr_store)
    print(f"  {len(dprr_persons)} persons")

    print("Loading EDH elite persons...")
    edh_persons = get_edh_elite_persons(edh_store)
    print(f"  {len(edh_persons)} persons")

    existing = load_existing_links()
    print(f"  {len(existing)} existing confirmed links")

    # Build nomen index to EXCLUDE known name matches (already tried)
    # We want to find matches that name matching MISSED
    dprr_nomen_set = set()
    for d in dprr_persons:
        nomen = re.sub(r"[()]", "", d.get("nomen", "")).strip().lower()
        if nomen:
            dprr_nomen_set.add(nomen)

    # Embed DPRR descriptions
    print("Embedding DPRR persons...")
    dprr_texts = [p["description"] for p in dprr_persons]
    dprr_embeddings = np.array(list(model.embed(dprr_texts)))
    print(f"  Shape: {dprr_embeddings.shape}")

    # Embed EDH names
    print("Embedding EDH persons...")
    edh_texts = [p["name"] for p in edh_persons]
    edh_embeddings = np.array(list(model.embed(edh_texts)))
    print(f"  Shape: {edh_embeddings.shape}")

    # Normalize for cosine similarity
    dprr_norms = np.linalg.norm(dprr_embeddings, axis=1, keepdims=True)
    edh_norms = np.linalg.norm(edh_embeddings, axis=1, keepdims=True)
    dprr_normed = dprr_embeddings / np.where(dprr_norms > 0, dprr_norms, 1)
    edh_normed = edh_embeddings / np.where(edh_norms > 0, edh_norms, 1)

    # Compute similarity matrix in batches (4876 × 6318 is manageable)
    print("Computing similarity matrix...")
    # Use batch dot product
    sim_matrix = dprr_normed @ edh_normed.T
    print(f"  Shape: {sim_matrix.shape}")

    # Find high-similarity pairs
    print("Finding high-similarity pairs...")
    threshold = 0.85  # High threshold for person names
    candidates = []

    for i in range(len(dprr_persons)):
        dprr = dprr_persons[i]
        dprr_uri = dprr["uri"]

        # Get top matches for this DPRR person
        scores = sim_matrix[i]
        top_indices = np.argsort(scores)[::-1][:10]

        for j in top_indices:
            score = scores[j]
            if score < threshold:
                break

            edh = edh_persons[j]
            edh_uri = edh["person"]

            # Skip existing links
            if (dprr_uri, edh_uri) in existing:
                continue

            # Check if this is a name-matching pair (nomen overlap)
            # We want to find pairs that name matching MISSED
            edh_name = edh["name"]
            edh_parts = edh_name.split()
            edh_nomen = edh_parts[1].lower().rstrip(".,;") if len(edh_parts) >= 2 and edh_parts[0].endswith(".") else (edh_parts[0].lower().rstrip(".,;") if edh_parts else "")
            dprr_nomen = re.sub(r"[()]", "", dprr.get("nomen", "")).strip().lower()

            # Flag whether this is a NEW match (nomen doesn't match exactly)
            nomen_match = edh_nomen == dprr_nomen
            is_new = not nomen_match

            candidates.append({
                "dprr_uri": dprr_uri,
                "edh_uri": edh_uri,
                "dprr_label": dprr["label"],
                "edh_name": edh_name,
                "score": float(score),
                "is_new": is_new,
                "nomen_match": nomen_match,
            })

    print(f"  {len(candidates)} pairs above threshold {threshold}")

    # Separate new discoveries from nomen-matching pairs
    new_discoveries = [c for c in candidates if c["is_new"]]
    nomen_matches = [c for c in candidates if not c["is_new"]]

    print(f"  {len(new_discoveries)} NEW (nomen mismatch — potential spelling variants)")
    print(f"  {len(nomen_matches)} nomen-matching (reinforces name-based results)")

    # Print new discoveries
    if new_discoveries:
        new_discoveries.sort(key=lambda c: -c["score"])
        print(f"\n{'=' * 130}")
        print("NEW SEMANTIC MATCHES (nomen differs — potential spelling variants, transliterations)")
        print(f"{'=' * 130}")
        print(f"{'Score':>6}  {'DPRR Label':<55}  {'EDH Name':<40}")
        print(f"{'-' * 130}")
        for c in new_discoveries[:100]:
            print(f"{c['score']:.3f}  {c['dprr_label'][:55]:<55}  {c['edh_name'][:40]:<40}")

    # Print top nomen-matching pairs not yet confirmed
    if nomen_matches:
        nomen_matches.sort(key=lambda c: -c["score"])
        print(f"\n{'=' * 130}")
        print("HIGH-CONFIDENCE NOMEN MATCHES (semantic similarity reinforces name match)")
        print(f"{'=' * 130}")
        print(f"{'Score':>6}  {'DPRR Label':<55}  {'EDH Name':<40}")
        print(f"{'-' * 130}")
        for c in nomen_matches[:50]:
            print(f"{c['score']:.3f}  {c['dprr_label'][:55]:<55}  {c['edh_name'][:40]:<40}")

    # Write new discoveries for review
    if new_discoveries:
        output_path = LINKAGE_DIR / "dprr_edh_semantic_candidates.yaml"
        yaml_data = {
            "metadata": {
                "source_dataset": "dprr",
                "target_dataset": "edh",
                "relationship": "skos:closeMatch",
                "confidence": "candidate",
                "method": "semantic_embedding_similarity",
                "basis": "BAAI/bge-small-en-v1.5 cosine similarity between DPRR person descriptions and EDH person names",
                "author": "linked-past project",
                "date": "2026-03-30",
            },
            "links": [
                {
                    "source": c["dprr_uri"],
                    "target": c["edh_uri"],
                    "note": f"DPRR: {c['dprr_label'][:60]}; EDH: {c['edh_name']}; similarity={c['score']:.3f}",
                }
                for c in new_discoveries
            ],
        }
        with output_path.open("w") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"\nWrote {len(new_discoveries)} semantic candidates to {output_path}")


if __name__ == "__main__":
    main()
