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

    def test_weight_redistribution_missing_signals(self):
        """When a signal has no data, its weight redistributes to others."""
        disambiguator = PersonDisambiguator()

        signals = {
            "filiation": SignalResult(0.0, 0.4, "no filiation", True),  # absent
            "career": SignalResult(1.0, 0.3, "consul confirmed", False),
            "geography": SignalResult(0.0, 0.2, "no findspot", True),  # absent
            "temporal": SignalResult(1.0, 0.1, "within era", False),
        }

        score = disambiguator._compute_weighted_score(signals)
        # career (0.3) + temporal (0.1) = 0.4 available → normalized to 1.0
        assert score == pytest.approx(1.0, abs=0.01)

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
