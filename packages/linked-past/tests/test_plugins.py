# tests/test_plugins.py
"""Parametrized tests covering all 7 dataset plugins."""

import pytest
from linked_past.core.store import create_store
from linked_past.datasets.base import ValidationResult
from linked_past.datasets.crro.plugin import CRROPlugin
from linked_past.datasets.dprr.plugin import DPRRPlugin
from linked_past.datasets.edh.plugin import EDHPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin
from linked_past.datasets.ocre.plugin import OCREPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.pleiades.plugin import PleiadesPlugin

# (PluginClass, expected_name, expected_license, required_prefix, schema_class_keywords, sample_turtle)
PLUGIN_SPECS = [
    (
        DPRRPlugin,
        "dprr",
        "CC BY-NC 4.0",
        "vocab",
        ["Person", "PostAssertion"],
        (
            '@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .\n'
            '<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person .\n'
        ),
    ),
    (
        PleiadesPlugin,
        "pleiades",
        "CC BY 3.0",
        "pleiades",
        ["Place", "Location"],
        (
            '@prefix pleiades: <https://pleiades.stoa.org/places/vocab#> .\n'
            '@prefix dcterms: <http://purl.org/dc/terms/> .\n'
            '<https://pleiades.stoa.org/places/423025> a pleiades:Place ;\n'
            '    dcterms:title "Roma" .\n'
        ),
    ),
    (
        PeriodOPlugin,
        "periodo",
        "CC0",
        "periodo",
        ["Period", "Authority"],
        (
            '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
            '@prefix time: <http://www.w3.org/2006/time#> .\n'
            '<http://n2t.net/ark:/99152/p05krdxmkzt> a skos:Concept, time:ProperInterval ;\n'
            '    skos:prefLabel "Roman Republic" .\n'
        ),
    ),
    (
        NomismaPlugin,
        "nomisma",
        "CC BY",
        "nmo",
        ["Person", "Mint"],
        (
            '@prefix nmo: <http://nomisma.org/ontology#> .\n'
            '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
            '<http://nomisma.org/id/rome> a nmo:Mint, skos:Concept ;\n'
            '    skos:prefLabel "Rome"@en .\n'
        ),
    ),
    (
        CRROPlugin,
        "crro",
        "ODbL 1.0",
        "nmo",
        ["CoinType", "TypeSeriesItem"],
        (
            '@prefix nmo: <http://nomisma.org/ontology#> .\n'
            '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
            '<http://numismatics.org/crro/id/rrc-1.1> a nmo:TypeSeriesItem, skos:Concept ;\n'
            '    skos:prefLabel "RRC 1/1" .\n'
        ),
    ),
    (
        OCREPlugin,
        "ocre",
        "ODbL 1.0",
        "nmo",
        ["CoinType", "TypeSeriesItem"],
        (
            '@prefix nmo: <http://nomisma.org/ontology#> .\n'
            '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
            '<http://numismatics.org/ocre/id/ric.1.aug.1A> a nmo:TypeSeriesItem, skos:Concept ;\n'
            '    skos:prefLabel "RIC I Augustus 1A" .\n'
        ),
    ),
    (
        EDHPlugin,
        "edh",
        "CC BY-SA 4.0",
        "epi",
        ["Inscription"],
        (
            '@prefix epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#> .\n'
            '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
            '<http://edh-www.adw.uni-heidelberg.de/edh/inschrift/HD000001> a epi:Inscription ;\n'
            '    skos:prefLabel "epitaph"@en .\n'
        ),
    ),
]


@pytest.fixture(params=PLUGIN_SPECS, ids=lambda s: s[1])
def plugin_spec(request):
    """Yield (plugin_instance, name, license, required_prefix, schema_keywords, sample_turtle)."""
    cls, name, lic, prefix, keywords, turtle = request.param
    plugin = cls()
    return plugin, name, lic, prefix, keywords, turtle


def test_plugin_attributes(plugin_spec):
    plugin, name, lic, _prefix, _keywords, _turtle = plugin_spec
    assert plugin.name == name
    assert plugin.license == lic
    assert plugin.display_name
    assert plugin.description
    assert plugin.url


def test_plugin_prefixes(plugin_spec):
    plugin, _name, _lic, prefix, _keywords, _turtle = plugin_spec
    prefixes = plugin.get_prefixes()
    assert isinstance(prefixes, dict)
    assert prefix in prefixes


def test_plugin_schema(plugin_spec):
    plugin, _name, _lic, _prefix, keywords, _turtle = plugin_spec
    schema = plugin.get_schema()
    assert isinstance(schema, str)
    for kw in keywords:
        assert kw in schema, f"Expected '{kw}' in schema for {plugin.name}"


def test_plugin_validate_valid(plugin_spec):
    plugin, _name, _lic, _prefix, _keywords, _turtle = plugin_spec
    prefixes = plugin.get_prefixes()
    prefix_block = "\n".join(f"PREFIX {k}: <{v}>" for k, v in prefixes.items())
    result = plugin.validate(f"{prefix_block}\nSELECT ?s WHERE {{ ?s ?p ?o }}")
    assert isinstance(result, ValidationResult)
    assert result.valid is True


def test_plugin_validate_unknown_class(plugin_spec):
    plugin, _name, _lic, prefix, _keywords, _turtle = plugin_spec
    prefixes = plugin.get_prefixes()
    ns = prefixes[prefix]
    result = plugin.validate(
        f"PREFIX {prefix}: <{ns}>\nSELECT ?s WHERE {{ ?s a {prefix}:CompletelyFakeClass999 }}"
    )
    # Unknown classes are warnings, not errors
    assert result.valid is True


def test_plugin_load(plugin_spec, tmp_path):
    plugin, name, _lic, _prefix, _keywords, turtle = plugin_spec
    ttl = tmp_path / f"{name}.ttl"
    ttl.write_text(turtle)
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_plugin_version_info(plugin_spec, tmp_path):
    plugin, _name, _lic, _prefix, _keywords, _turtle = plugin_spec
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert info.rdf_format == "turtle"
