"""Tests for prosopographic disambiguation signals."""

import pytest
from linked_past.core.disambiguate import (
    score_career,
    score_filiation,
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
