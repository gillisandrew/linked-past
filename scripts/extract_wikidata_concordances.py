"""Extract cross-dataset concordances from Wikidata as Turtle for the linkage graph.

Queries Wikidata SPARQL endpoint for entities that bridge our datasets via
shared identifiers, and produces Turtle files loadable into the linkage graph.

Usage:
    uv run python scripts/extract_wikidata_concordances.py [output_dir]
"""

import sys
import urllib.parse
import urllib.request
from pathlib import Path

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# Pleiades ↔ Trismegistos Place concordance
PLEIADES_TM_QUERY = """\
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

CONSTRUCT {
    ?pleiades_uri skos:exactMatch ?tm_uri .
}
WHERE {
    ?item wdt:P1584 ?pleiades .
    ?item wdt:P1958 ?tm_place .
    BIND(IRI(CONCAT("https://pleiades.stoa.org/places/", ?pleiades)) AS ?pleiades_uri)
    BIND(IRI(CONCAT("https://www.trismegistos.org/place/", ?tm_place)) AS ?tm_uri)
}
"""

# Nomisma ↔ Pleiades via shared Wikidata entities
NOMISMA_PLEIADES_QUERY = """\
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

CONSTRUCT {
    ?nomisma_uri skos:exactMatch ?pleiades_uri .
}
WHERE {
    ?item wdt:P2950 ?nomisma_id .
    ?item wdt:P1584 ?pleiades .
    BIND(IRI(CONCAT("http://nomisma.org/id/", ?nomisma_id)) AS ?nomisma_uri)
    BIND(IRI(CONCAT("https://pleiades.stoa.org/places/", ?pleiades)) AS ?pleiades_uri)
}
"""

QUERIES = {
    "pleiades_tm_places.ttl": PLEIADES_TM_QUERY,
    "nomisma_pleiades.ttl": NOMISMA_PLEIADES_QUERY,
}


def run_construct(query: str) -> bytes:
    """Run a SPARQL CONSTRUCT query against Wikidata, return Turtle bytes."""
    params = urllib.parse.urlencode({"query": query, "format": "text/turtle"})
    url = f"{WIKIDATA_ENDPOINT}?{params}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "text/turtle", "User-Agent": "linked-past/0.1 (https://github.com/gillisandrew/dprr-tool)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def main(output_dir: str = "linked_past/linkages/wikidata"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for filename, query in QUERIES.items():
        print(f"Running {filename}...")
        try:
            data = run_construct(query)
            path = out / filename
            path.write_bytes(data)
            lines = data.decode("utf-8", errors="replace").count("\n")
            print(f"  Wrote {path} ({len(data):,} bytes, ~{lines} lines)")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("Done. Load these into the linkage graph or linkages/ directory.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "linked_past/linkages/wikidata")
