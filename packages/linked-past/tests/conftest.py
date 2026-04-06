# tests/conftest.py
"""Shared integration test fixtures."""

import pytest
from linked_past.core.server import build_app_context

DPRR_SAMPLE_TURTLE = """\
@prefix dprr: <http://romanrepublic.ac.uk/rdf/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a dprr:Person ;
    dprr:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    dprr:hasDprrID "IUNI0001" ;
    dprr:hasNomen "Iunius" ;
    dprr:hasCognomen "Brutus" ;
    dprr:isSex <http://romanrepublic.ac.uk/rdf/entity/Sex/Male> ;
    dprr:hasEraFrom "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/1> a dprr:PostAssertion ;
    dprr:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    dprr:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/3> ;
    dprr:hasDateStart "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Office/3> a dprr:Office ;
    rdfs:label "Office: consul" .

<http://romanrepublic.ac.uk/rdf/entity/Sex/Male> a dprr:Sex ;
    rdfs:label "Sex: Male" .
"""

MINIMAL_TURTLE = "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"

ALL_DATASETS = ("dprr", "pleiades", "periodo", "nomisma", "crro", "ocre", "rpc", "edh")


@pytest.fixture
def patched_app_context(tmp_path, monkeypatch):
    """Build an AppContext with all plugins, using local TTL fixtures."""
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))

    # Write TTL files: rich data for DPRR, minimal stubs for others
    for dataset in ALL_DATASETS:
        ds_dir = tmp_path / dataset
        ds_dir.mkdir()
        content = DPRR_SAMPLE_TURTLE if dataset == "dprr" else MINIMAL_TURTLE
        (ds_dir / f"{dataset}.ttl").write_text(content)

    # Patch fetch on every plugin to return the local file
    for dataset in ALL_DATASETS:
        plugin_module = {
            "dprr": "linked_past.datasets.dprr.plugin.DPRRPlugin",
            "pleiades": "linked_past.datasets.pleiades.plugin.PleiadesPlugin",
            "periodo": "linked_past.datasets.periodo.plugin.PeriodOPlugin",
            "nomisma": "linked_past.datasets.nomisma.plugin.NomismaPlugin",
            "crro": "linked_past.datasets.crro.plugin.CRROPlugin",
            "ocre": "linked_past.datasets.ocre.plugin.OCREPlugin",
            "rpc": "linked_past.datasets.rpc.plugin.RPCPlugin",
            "edh": "linked_past.datasets.edh.plugin.EDHPlugin",
        }[dataset]
        monkeypatch.setattr(
            f"{plugin_module}.fetch",
            lambda self, data_dir, force=False, _ds=dataset: data_dir / f"{_ds}.ttl",
        )

    return build_app_context(eager=True, skip_search=True)
