"""Tests for DPRR→Pleiades province linkage completeness and URI consistency."""

from pathlib import Path

import yaml

LINKAGE_FILE = (
    Path(__file__).resolve().parents[1]
    / "linked_past"
    / "linkages"
    / "dprr_pleiades.yaml"
)


def _load_links() -> dict:
    with LINKAGE_FILE.open() as f:
        return yaml.safe_load(f)


def test_minimum_link_count():
    """We should have at least 55 province→place links."""
    data = _load_links()
    assert len(data["links"]) >= 55, (
        f"Expected >=55 links, got {len(data['links'])}"
    )


def test_source_uris_use_numeric_ids():
    """All source URIs must use the numeric Province ID form that matches the DPRR Oxigraph store."""
    data = _load_links()
    for link in data["links"]:
        source = link["source"]
        # Must be http://romanrepublic.ac.uk/rdf/entity/Province/{number}
        suffix = source.replace("http://romanrepublic.ac.uk/rdf/entity/Province/", "")
        assert suffix.isdigit(), (
            f"Source URI {source} does not use numeric ID — "
            f"slug-based URIs don't match the DPRR store"
        )


def test_target_uris_use_pleiades_this_fragment():
    """All target URIs must use the https://pleiades.stoa.org/places/{id}#this pattern."""
    data = _load_links()
    for link in data["links"]:
        target = link["target"]
        assert target.startswith("https://pleiades.stoa.org/places/"), (
            f"Target {target} is not a Pleiades place URI"
        )
        assert target.endswith("#this"), (
            f"Target {target} missing #this fragment"
        )


def test_no_duplicate_sources():
    """Each DPRR province should appear at most once as a source."""
    data = _load_links()
    sources = [link["source"] for link in data["links"]]
    duplicates = [s for s in sources if sources.count(s) > 1]
    assert not duplicates, f"Duplicate sources: {set(duplicates)}"


def test_metadata_fields():
    """Metadata must have required fields."""
    data = _load_links()
    meta = data["metadata"]
    assert meta["source_dataset"] == "dprr"
    assert meta["target_dataset"] == "pleiades"
    assert meta["relationship"] == "skos:closeMatch"
    assert meta["confidence"] == "confirmed"
