"""Tests for prosopographic disambiguation signals."""

import pytest
from linked_past.core.disambiguate import (
    PersonDisambiguator,
    SignalResult,
    extract_context_from_edh_uri,
    extract_context_from_fields,
    score_career,
    score_filiation,
    score_geography,
    score_temporal,
)


class TestScoreTemporal:
    def test_midpoint_within_era(self):
        score, explanation, is_absent = score_temporal(era_from=-185, era_to=-129, date_start=-150, date_end=-140)
        assert score == 1.0
        assert not is_absent

    def test_partial_overlap(self):
        score, explanation, is_absent = score_temporal(era_from=-100, era_to=0, date_start=0, date_end=50)
        assert score == 0.5
        assert not is_absent

    def test_no_overlap(self):
        score, explanation, is_absent = score_temporal(era_from=-300, era_to=-200, date_start=100, date_end=150)
        assert score == 0.0
        assert not is_absent

    def test_no_inscription_date(self):
        score, explanation, is_absent = score_temporal(era_from=-185, era_to=-129, date_start=None, date_end=None)
        assert score == 0.0
        assert is_absent

    def test_no_era_data(self):
        score, explanation, is_absent = score_temporal(era_from=None, era_to=None, date_start=-147, date_end=-140)
        assert score == 0.0
        assert is_absent


class TestScoreCareer:
    def test_exact_office_and_date(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office="consul", date=-147)
        assert score == 1.0
        assert not is_absent

    def test_office_match_close_date(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office="consul", date=-140)
        assert score == 0.7

    def test_office_match_no_date(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office="consul", date=None)
        assert score == 0.5

    def test_office_not_held(self):
        offices = [{"office": "Office: praetor", "date_start": -150}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office="consul", date=-147)
        assert score == 0.3

    def test_cursus_age_violation(self):
        offices = [{"office": "Office: consul", "date_start": -130}]
        score, explanation, is_absent = score_career(offices, era_from=-150, office="consul", date=-130)
        assert score == 0.0

    def test_office_before_birth(self):
        offices = [{"office": "Office: consul", "date_start": -200}]
        score, explanation, is_absent = score_career(offices, era_from=-150, office="consul", date=-200)
        assert score == 0.0
        assert "before birth" in explanation or "impossible" in explanation

    def test_no_office_in_inscription(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office=None, date=None)
        assert score == 0.0
        assert is_absent

    def test_no_dprr_offices(self):
        score, explanation, is_absent = score_career([], era_from=-185, office="consul", date=-147)
        assert score == 0.0


class TestScoreFiliation:
    def test_father_and_grandfather_match(self):
        family = {"father_praenomen": "manius", "grandfather_praenomen": "manius"}
        score, explanation, is_absent = score_filiation(family, {"father": "manius", "grandfather": "manius"})
        assert score == 1.0
        assert not is_absent

    def test_father_match_only(self):
        family = {"father_praenomen": "lucius", "grandfather_praenomen": None}
        score, explanation, is_absent = score_filiation(family, {"father": "lucius"})
        assert score == 0.5

    def test_father_mismatch(self):
        family = {"father_praenomen": "marcus", "grandfather_praenomen": None}
        score, explanation, is_absent = score_filiation(family, {"father": "lucius"})
        assert score == 0.0
        assert not is_absent  # data present, just doesn't match

    def test_no_filiation_data(self):
        family = {"father_praenomen": "marcus", "grandfather_praenomen": None}
        score, explanation, is_absent = score_filiation(family, {})
        assert score == 0.0
        assert is_absent

    def test_no_family_data(self):
        family = {}
        score, explanation, is_absent = score_filiation(family, {"father": "marcus"})
        assert score == 0.0
        assert is_absent


class TestScoreGeography:
    def test_province_match(self):
        provinces = ["https://pleiades.stoa.org/places/837#this"]
        score, explanation, is_absent = score_geography(provinces, "https://pleiades.stoa.org/places/837#this")
        assert score == 1.0
        assert not is_absent

    def test_no_match(self):
        provinces = ["https://pleiades.stoa.org/places/775#this"]  # Africa
        score, explanation, is_absent = score_geography(provinces, "https://pleiades.stoa.org/places/837#this")  # Asia
        assert score == 0.0
        assert not is_absent  # data present, just doesn't match

    def test_no_findspot(self):
        provinces = ["https://pleiades.stoa.org/places/837#this"]
        score, explanation, is_absent = score_geography(provinces, None)
        assert score == 0.0
        assert is_absent

    def test_no_provinces(self):
        score, explanation, is_absent = score_geography([], "https://pleiades.stoa.org/places/837#this")
        assert score == 0.0
        assert is_absent

    def test_italy_fallback(self):
        score, explanation, is_absent = score_geography([], None, is_italian_findspot=True, has_italian_career=True)
        assert score == 0.0  # no findspot URI → absent
        assert is_absent

    def test_italy_career_italian_findspot(self):
        score, explanation, is_absent = score_geography(
            [], "https://pleiades.stoa.org/places/423025#this",
            is_italian_findspot=True, has_italian_career=True,
        )
        assert score == 0.3
        assert not is_absent


class TestPersonDisambiguator:
    def test_weighted_combination(self):
        """Test that the orchestrator combines signal scores correctly."""
        disambiguator = PersonDisambiguator()

        # Candidate A: filiation match + career match
        signals_a = {
            "filiation": SignalResult(1.0, 0.4, "father+grandfather match", False),
            "career": SignalResult(1.0, 0.3, "consul -147 confirmed", False),
            "geography": SignalResult(0.0, 0.2, "no findspot", True),
            "temporal": SignalResult(1.0, 0.1, "within era", False),
        }
        # Candidate B: only temporal overlap
        signals_b = {
            "filiation": SignalResult(0.0, 0.4, "father mismatch", False),
            "career": SignalResult(0.0, 0.3, "office not held", False),
            "geography": SignalResult(0.0, 0.2, "no findspot", True),
            "temporal": SignalResult(1.0, 0.1, "within era", False),
        }

        score_a = disambiguator._compute_weighted_score(signals_a)
        score_b = disambiguator._compute_weighted_score(signals_b)

        assert score_a > 0.7
        assert score_b < 0.2
        assert score_a > score_b

    def test_coverage_penalty_for_sparse_evidence(self):
        """When most signals are absent, score is penalized by coverage factor."""
        disambiguator = PersonDisambiguator()

        signals = {
            "filiation": SignalResult(0.0, 0.4, "no filiation", True),
            "career": SignalResult(1.0, 0.3, "consul confirmed", False),
            "geography": SignalResult(0.0, 0.2, "no findspot", True),
            "temporal": SignalResult(1.0, 0.1, "within era", False),
        }

        score = disambiguator._compute_weighted_score(signals)
        # raw = 1.0, coverage = 0.4/1.0 = 0.4 → final = 0.4
        assert score == pytest.approx(0.4, abs=0.01)

    def test_full_evidence_no_penalty(self):
        """With all signals present, coverage = 1.0, no penalty."""
        disambiguator = PersonDisambiguator()
        signals = {
            "filiation": SignalResult(1.0, 0.4, "match", False),
            "career": SignalResult(1.0, 0.3, "match", False),
            "geography": SignalResult(1.0, 0.2, "match", False),
            "temporal": SignalResult(1.0, 0.1, "match", False),
        }
        assert disambiguator._compute_weighted_score(signals) == pytest.approx(1.0, abs=0.01)

    def test_single_signal_heavily_penalized(self):
        """A candidate with only temporal signal should score much lower."""
        disambiguator = PersonDisambiguator()
        signals = {
            "filiation": SignalResult(0.0, 0.4, "absent", True),
            "career": SignalResult(0.0, 0.3, "absent", True),
            "geography": SignalResult(0.0, 0.2, "absent", True),
            "temporal": SignalResult(1.0, 0.1, "within era", False),
        }
        # raw = 1.0, coverage = 0.1/1.0 = 0.1 → final = 0.1
        assert disambiguator._compute_weighted_score(signals) == pytest.approx(0.1, abs=0.01)

    def test_all_signals_absent(self):
        """When all signals are absent, score is 0."""
        disambiguator = PersonDisambiguator()
        signals = {
            "filiation": SignalResult(0.0, 0.4, "absent", True),
            "career": SignalResult(0.0, 0.3, "absent", True),
            "geography": SignalResult(0.0, 0.2, "absent", True),
            "temporal": SignalResult(0.0, 0.1, "absent", True),
        }
        assert disambiguator._compute_weighted_score(signals) == 0.0

    def test_confidence_strong(self):
        assert PersonDisambiguator._classify_confidence(0.8, 0.3) == "strong"

    def test_confidence_probable(self):
        assert PersonDisambiguator._classify_confidence(0.6, 0.15) == "probable"

    def test_confidence_ambiguous(self):
        assert PersonDisambiguator._classify_confidence(0.4, 0.05) == "ambiguous"


class TestExtractContextFromFields:
    def test_basic_latin_name(self):
        ctx = extract_context_from_fields(
            name="P. Cornelius Scipio",
            filiation="P. f. Cn. n.",
            office="cos.",
            date=-147,
        )
        assert ctx.praenomen == "publius"
        assert ctx.nomen == "Cornelius"
        assert ctx.cognomen == "Scipio"
        assert ctx.filiation == "P. f. Cn. n."
        assert ctx.office == "consul"
        assert ctx.date_start == -147
        assert ctx.date_end == -147

    def test_greek_name_transliterated(self):
        ctx = extract_context_from_fields(name="Κ. Ἀνχάριος")
        assert ctx.praenomen is not None  # κ → c → gaius or quintus
        assert "ancharius" in ctx.normalized_name.lower() or "anchar" in ctx.normalized_name.lower()

    def test_no_optional_fields(self):
        ctx = extract_context_from_fields(name="Aquillius")
        assert ctx.name == "Aquillius"
        assert ctx.office is None
        assert ctx.filiation is None
        assert ctx.date_start is None


class TestExtractContextFromEDH:
    def test_returns_none_for_missing_uri(self):
        """With an empty in-memory store, extraction returns None."""
        from pyoxigraph import Store as OxStore
        store = OxStore()
        result = extract_context_from_edh_uri("https://example.org/nonexistent", store)
        assert result is None


# ── Aquillius golden integration test ───────────────────────────────────────

AQUILLIUS_TURTLE = """\
@prefix dprr: <http://romanrepublic.ac.uk/rdf/ontology#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .

# Praenomen: Manius
<http://romanrepublic.ac.uk/rdf/entity/Praenomen/1> a dprr:Praenomen ;
    rdfs:label "Praenomen: M'." .

# ── Person 1614: M'. Aquillius cos. 129 BCE ──────────────────────────────
<http://romanrepublic.ac.uk/rdf/entity/Person/1614> a dprr:Person ;
    dprr:hasPersonName "AQUI1614 M'. Aquillius (10) M'. f. M'. n." ;
    dprr:hasNomen "Aquillius" ;
    dprr:hasPraenomen <http://romanrepublic.ac.uk/rdf/entity/Praenomen/1> ;
    dprr:hasEraFrom "-185"^^xsd:integer ;
    dprr:hasEraTo   "-129"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/1614a> a dprr:PostAssertion ;
    dprr:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1614> ;
    dprr:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/consul> ;
    dprr:hasDateStart "-129"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Office/consul> a dprr:Office ;
    rdfs:label "Office: consul" .

# ── Person 1757: M'. Aquillius cos. 101 BCE ──────────────────────────────
<http://romanrepublic.ac.uk/rdf/entity/Person/1757> a dprr:Person ;
    dprr:hasPersonName "AQUI1757 M'. Aquillius (11) M'. f. M'. n." ;
    dprr:hasNomen "Aquillius" ;
    dprr:hasPraenomen <http://romanrepublic.ac.uk/rdf/entity/Praenomen/1> ;
    dprr:hasEraFrom "-155"^^xsd:integer ;
    dprr:hasEraTo   "-101"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/1757a> a dprr:PostAssertion ;
    dprr:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1757> ;
    dprr:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/consul> ;
    dprr:hasDateStart "-101"^^xsd:integer .

# ── Person 4686: L. Aquillius M. f. M. n. Florus q. c.70 BCE ────────────
<http://romanrepublic.ac.uk/rdf/entity/Person/4686> a dprr:Person ;
    dprr:hasPersonName "AQUI4686 L. Aquillius (12) M'. f. M'. n. Florus" ;
    dprr:hasNomen "Aquillius" ;
    dprr:hasPraenomen <http://romanrepublic.ac.uk/rdf/entity/Praenomen/lucius> ;
    dprr:hasEraFrom "-115"^^xsd:integer ;
    dprr:hasEraTo   "-60"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Praenomen/lucius> a dprr:Praenomen ;
    rdfs:label "Praenomen: L." .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/4686a> a dprr:PostAssertion ;
    dprr:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/4686> ;
    dprr:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/quaestor> ;
    dprr:hasDateStart "-70"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Office/quaestor> a dprr:Office ;
    rdfs:label "Office: quaestor" .

# ── Relationship: 1614 is father of 1757 ────────────────────────────────
<http://romanrepublic.ac.uk/rdf/entity/Relationship/fatherOf> a dprr:Relationship ;
    rdfs:label "Relationship: father of" .

<http://romanrepublic.ac.uk/rdf/entity/RelationshipAssertion/ra1> a dprr:RelationshipAssertion ;
    dprr:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1614> ;
    dprr:hasRelatedPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1757> ;
    dprr:hasRelationship <http://romanrepublic.ac.uk/rdf/entity/Relationship/fatherOf> .

# ── Relationship: 1757 is father of 4686 ────────────────────────────────
<http://romanrepublic.ac.uk/rdf/entity/RelationshipAssertion/ra2> a dprr:RelationshipAssertion ;
    dprr:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1757> ;
    dprr:hasRelatedPerson <http://romanrepublic.ac.uk/rdf/entity/Person/4686> ;
    dprr:hasRelationship <http://romanrepublic.ac.uk/rdf/entity/Relationship/fatherOf> .
"""

_DPRR_BASE = "http://romanrepublic.ac.uk/rdf/entity/Person/"


@pytest.fixture
def aquillius_store(tmp_path):
    """Ephemeral Oxigraph store pre-loaded with the Aquillius family fixture."""
    from pyoxigraph import RdfFormat
    from pyoxigraph import Store as OxStore

    store = OxStore()
    store.bulk_load(
        input=AQUILLIUS_TURTLE.encode(),
        format=RdfFormat.TURTLE,
    )
    return store


class TestAquilliusGolden:
    """Golden integration tests using the Aquillius family fixture."""

    def test_filiation_scores_1_for_florus(self, aquillius_store):
        """Person/4686 (Florus): father=manius, grandfather=manius — filiation score = 1.0."""
        from linked_past.core.disambiguate import fetch_dprr_family, score_filiation

        family = fetch_dprr_family(aquillius_store, f"{_DPRR_BASE}4686")
        assert family["father_praenomen"] == "manius", f"Expected manius, got {family['father_praenomen']}"
        assert family["grandfather_praenomen"] == "manius", f"Expected manius, got {family['grandfather_praenomen']}"

        inscription_filiation = {"father": "manius", "grandfather": "manius"}
        score, explanation, is_absent = score_filiation(family, inscription_filiation)
        assert score == 1.0, f"Expected 1.0 but got {score}: {explanation}"
        assert not is_absent

    def test_career_scores_for_quaestor(self, aquillius_store):
        """Person/4686: held quaestor at -70 — career score >= 0.7."""
        from linked_past.core.disambiguate import fetch_dprr_offices, score_career

        offices = fetch_dprr_offices(aquillius_store, f"{_DPRR_BASE}4686")
        assert any("quaestor" in (o.get("office") or "").lower() for o in offices), \
            f"Quaestor office not found in: {offices}"

        score, explanation, is_absent = score_career(
            dprr_offices=offices,
            era_from=-115,
            office="quaestor",
            date=-70,
        )
        assert score >= 0.7, f"Expected >= 0.7 but got {score}: {explanation}"
        assert not is_absent

    def test_florus_ranks_above_grandfather(self, aquillius_store):
        """Full disambiguation: inscription for quaestor ~70 BCE ranks Person/4686 first."""
        from linked_past.core.disambiguate import (
            WEIGHTS,
            PersonDisambiguator,
            SignalResult,
            fetch_dprr_candidates,
            fetch_dprr_family,
            fetch_dprr_offices,
            fetch_dprr_province_pleiades,
            score_career,
            score_filiation,
            score_geography,
            score_temporal,
        )
        from linked_past.core.onomastics import parse_filiation

        # Inscription context: quaestor ~70 BCE, father=manius, grandfather=manius
        inscription_filiation = parse_filiation("M'. f. M'. n.")
        person_office = "quaestor"
        person_date = -70

        candidates = fetch_dprr_candidates(aquillius_store, "Aquillius")
        assert len(candidates) == 3, f"Expected 3 candidates, got {len(candidates)}"

        disambiguator = PersonDisambiguator()
        candidates_signals = []

        for cand in candidates:
            cand_uri = cand.get("person", "")
            cand_label = cand.get("label", cand_uri)
            era_from_raw = cand.get("eraFrom")
            era_to_raw = cand.get("eraTo")
            try:
                era_from = int(era_from_raw) if era_from_raw else None
            except (ValueError, TypeError):
                era_from = None
            try:
                era_to = int(era_to_raw) if era_to_raw else None
            except (ValueError, TypeError):
                era_to = None

            dprr_offices = fetch_dprr_offices(aquillius_store, cand_uri)
            dprr_family = fetch_dprr_family(aquillius_store, cand_uri)
            province_pleiades = fetch_dprr_province_pleiades(aquillius_store, None, cand_uri)

            t_score, t_expl, t_absent = score_temporal(era_from, era_to, person_date, person_date)
            c_score, c_expl, c_absent = score_career(dprr_offices, era_from, person_office, person_date)
            f_score, f_expl, f_absent = score_filiation(dprr_family, inscription_filiation)
            g_score, g_expl, g_absent = score_geography(province_pleiades, None)

            signals = {
                "filiation": SignalResult(f_score, WEIGHTS["filiation"], f_expl, f_absent),
                "career":    SignalResult(c_score, WEIGHTS["career"],    c_expl, c_absent),
                "geography": SignalResult(g_score, WEIGHTS["geography"], g_expl, g_absent),
                "temporal":  SignalResult(t_score, WEIGHTS["temporal"],  t_expl, t_absent),
            }
            candidates_signals.append((cand_uri, cand_label, signals))

        ranked = disambiguator.rank_candidates(candidates_signals)
        assert len(ranked) == 3

        top = ranked[0]
        assert top.dprr_uri == f"{_DPRR_BASE}4686", (
            f"Expected Person/4686 to rank first, but got {top.dprr_uri} "
            f"(score {top.score:.3f}). Full ranking: "
            + ", ".join(f"{m.dprr_uri.rsplit('/', 1)[-1]}={m.score:.3f}" for m in ranked)
        )
