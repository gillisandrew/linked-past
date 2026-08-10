"""Tests for the truncated subresource reference fix (Pleiades ingest)."""

from scripts.fix_pleiades_refs import fix_truncated_refs

SINGLE_LINE = """\
<https://pleiades.stoa.org/places/305120> a pleiades:Place;
    dcterms:title "Numidia (region)";
    pleiades:hasLocation <https://pleiades.stoa.org/places/batlas-map-label-location>;
    pleiades:hasName <https://pleiades.stoa.org/places/numidia> .
"""

MULTI_LINE_LIST = """\
<https://pleiades.stoa.org/places/108728> a pleiades:Place;
    pleiades:hasLocation <https://pleiades.stoa.org/places/batlas-location>,
        <https://pleiades.stoa.org/places/osm-location>;
    dcterms:title "Somewhere" .
"""

ERRATA = """\
<https://pleiades.stoa.org/errata/991368> a pleiades:Place;
    pleiades:hasLocation <https://pleiades.stoa.org/errata/osm-location>;
    pleiades:hasName <https://pleiades.stoa.org/errata/macedonia> .
"""

ALREADY_CORRECT = """\
<https://pleiades.stoa.org/places/305120> a pleiades:Place;
    pleiades:hasLocation <https://pleiades.stoa.org/places/305120/batlas-map-label-location>;
    pleiades:hasName <https://pleiades.stoa.org/places/305120/numidia> .
"""

OTHER_PREDICATES_UNTOUCHED = """\
<https://pleiades.stoa.org/places/305120> a pleiades:Place;
    skos:inScheme <https://pleiades.stoa.org/places>;
    pleiades:hasFeatureType <https://pleiades.stoa.org/vocabularies/place-types/region>;
    rdfs:seeAlso <https://pleiades.stoa.org/places/295279>;
    pleiades:hasName <https://pleiades.stoa.org/places/numidia> .
"""

SUBJECT_LINE_PREDICATE = """\
<https://pleiades.stoa.org/places/42> pleiades:hasName <https://pleiades.stoa.org/places/answer>;
    dcterms:title "The Answer" .
"""


def test_single_line_refs_rewritten():
    fixed, count = fix_truncated_refs(SINGLE_LINE)
    assert count == 2
    assert "<https://pleiades.stoa.org/places/305120/batlas-map-label-location>" in fixed
    assert "<https://pleiades.stoa.org/places/305120/numidia>" in fixed
    assert "<https://pleiades.stoa.org/places/batlas-map-label-location>" not in fixed


def test_multi_line_object_list_rewritten():
    fixed, count = fix_truncated_refs(MULTI_LINE_LIST)
    assert count == 2
    assert "<https://pleiades.stoa.org/places/108728/batlas-location>" in fixed
    assert "<https://pleiades.stoa.org/places/108728/osm-location>" in fixed


def test_errata_scheme_rewritten():
    fixed, count = fix_truncated_refs(ERRATA)
    assert count == 2
    assert "<https://pleiades.stoa.org/errata/991368/osm-location>" in fixed
    assert "<https://pleiades.stoa.org/errata/991368/macedonia>" in fixed


def test_correct_refs_untouched():
    fixed, count = fix_truncated_refs(ALREADY_CORRECT)
    assert count == 0
    assert fixed == ALREADY_CORRECT


def test_other_predicates_untouched():
    fixed, count = fix_truncated_refs(OTHER_PREDICATES_UNTOUCHED)
    assert count == 1  # only the hasName ref
    assert "skos:inScheme <https://pleiades.stoa.org/places>;" in fixed
    assert "rdfs:seeAlso <https://pleiades.stoa.org/places/295279>;" in fixed
    assert "<https://pleiades.stoa.org/places/305120/numidia>" in fixed


def test_predicate_on_subject_line():
    fixed, count = fix_truncated_refs(SUBJECT_LINE_PREDICATE)
    assert count == 1
    assert "<https://pleiades.stoa.org/places/42/answer>" in fixed
