"""Tests for issuer-name enrichment of coin type labels."""

from pyoxigraph import RdfFormat, Store

from linked_past.datasets.coin_types import issuer_enriched_labels
from linked_past.datasets.crro.plugin import CRROPlugin
from linked_past.datasets.ocre.plugin import OCREPlugin

CRRO_TURTLE = """\
@prefix nmo: <http://nomisma.org/ontology#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<http://numismatics.org/crro/id/rrc-366.1> a nmo:TypeSeriesItem ;
    skos:prefLabel "RRC 366/1" ;
    nmo:hasIssuer <http://nomisma.org/id/c_annius> .
<http://numismatics.org/crro/id/rrc-1.1> a nmo:TypeSeriesItem ;
    skos:prefLabel "RRC 1/1" ;
    nmo:hasIssuer <http://nomisma.org/id/unknown_issuer> .
"""

NOMISMA_TURTLE = """\
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<http://nomisma.org/id/c_annius> skos:prefLabel "C. Annius"@en , "Gaius Annius"@de .
<http://nomisma.org/id/unknown_issuer> skos:prefLabel "Unbekannt"@de .
"""


class FakeRegistry:
    def __init__(self, stores: dict[str, Store]):
        self._stores = stores

    def get_store(self, name: str) -> Store:
        if name not in self._stores:
            raise KeyError(name)
        return self._stores[name]


def _store(turtle: str) -> Store:
    store = Store()
    store.bulk_load(turtle.encode(), format=RdfFormat.TURTLE)
    return store


def test_enriches_label_with_english_issuer_name():
    crro = _store(CRRO_TURTLE)
    registry = FakeRegistry({"nomisma": _store(NOMISMA_TURTLE)})

    rows = issuer_enriched_labels("crro", crro, registry)

    assert rows == [("entity_label", "RRC 366/1 — C. Annius\thttp://numismatics.org/crro/id/rrc-366.1")]


def test_issuer_without_english_label_is_skipped():
    crro = _store(CRRO_TURTLE)
    registry = FakeRegistry({"nomisma": _store(NOMISMA_TURTLE)})

    rows = issuer_enriched_labels("crro", crro, registry)

    assert all("rrc-1.1" not in text for _, text in rows)


def test_missing_nomisma_returns_empty():
    crro = _store(CRRO_TURTLE)
    assert issuer_enriched_labels("crro", crro, FakeRegistry({})) == []
    assert issuer_enriched_labels("crro", crro, None) == []


def test_crro_and_ocre_plugins_use_helper():
    crro = _store(CRRO_TURTLE)
    registry = FakeRegistry({"nomisma": _store(NOMISMA_TURTLE)})

    assert len(CRROPlugin().extra_search_entries(crro, registry)) == 1
    assert len(OCREPlugin().extra_search_entries(crro, registry)) == 1
