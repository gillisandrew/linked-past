# tests/test_server.py
from linked_past.core.server import build_app_context, create_mcp_server

SAMPLE_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    vocab:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    vocab:hasDprrID "IUNI0001" ;
    vocab:hasNomen "Iunius" .
"""


def test_build_app_context(tmp_path, monkeypatch):
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    dprr_dir = tmp_path / "dprr"
    dprr_dir.mkdir()
    (dprr_dir / "dprr.ttl").write_text(SAMPLE_TURTLE)
    monkeypatch.setattr(
        "linked_past.datasets.dprr.plugin.DPRRPlugin.fetch",
        lambda self, data_dir: data_dir / "dprr.ttl",
    )
    # Create minimal TTL files and patch fetch for other plugins
    for dataset in ("pleiades", "periodo", "nomisma"):
        ds_dir = tmp_path / dataset
        ds_dir.mkdir()
        (ds_dir / f"{dataset}.ttl").write_text(
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        )
    monkeypatch.setattr(
        "linked_past.datasets.pleiades.plugin.PleiadesPlugin.fetch",
        lambda self, data_dir: data_dir / "pleiades.ttl",
    )
    monkeypatch.setattr(
        "linked_past.datasets.periodo.plugin.PeriodOPlugin.fetch",
        lambda self, data_dir: data_dir / "periodo.ttl",
    )
    monkeypatch.setattr(
        "linked_past.datasets.nomisma.plugin.NomismaPlugin.fetch",
        lambda self, data_dir: data_dir / "nomisma.ttl",
    )
    ctx = build_app_context()
    assert "dprr" in ctx.registry.list_datasets()
    store = ctx.registry.get_store("dprr")
    assert store is not None


def test_create_mcp_server():
    mcp = create_mcp_server()
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "discover_datasets" in tool_names
    assert "get_schema" in tool_names
    assert "validate_sparql" in tool_names
    assert "query" in tool_names
