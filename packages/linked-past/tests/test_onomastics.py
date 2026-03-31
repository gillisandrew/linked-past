"""Tests for Roman onomastics: name parsing, praenomen normalization, Greek transliteration."""

from linked_past.core.onomastics import (
    is_greek,
    normalize_praenomen,
    parse_filiation,
    parse_office,
    parse_roman_name,
    transliterate_greek,
)


class TestNormalizePraenomen:
    def test_latin_abbreviated(self):
        assert normalize_praenomen("C.") == "gaius"
        assert normalize_praenomen("Cn.") == "gnaeus"
        assert normalize_praenomen("M'.") == "manius"

    def test_latin_without_dot(self):
        assert normalize_praenomen("L") == "lucius"

    def test_greek_full(self):
        assert normalize_praenomen("Γάιος") == "gaius"
        assert normalize_praenomen("Λεύκιος") == "lucius"
        assert normalize_praenomen("Κόιντος") == "quintus"

    def test_unknown_returns_none(self):
        assert normalize_praenomen("Flavius") is None


class TestParseRomanName:
    def test_tria_nomina(self):
        result = parse_roman_name("P. Cornelius Scipio")
        assert result["praenomen"] == "publius"
        assert result["nomen"] == "Cornelius"
        assert result["cognomen"] == "Scipio"

    def test_nomen_only(self):
        result = parse_roman_name("Cornelius")
        assert result.get("praenomen") is None
        assert result["nomen"] == "Cornelius"

    def test_with_filiation_skipped(self):
        result = parse_roman_name("L. Aquillius M. f. M. n. Florus")
        assert result["praenomen"] == "lucius"
        assert result["nomen"] == "Aquillius"
        assert result["cognomen"] == "Florus"

    def test_dprr_label_format(self):
        result = parse_roman_name("AQUI1614 M'. Aquillius (10) M'. f. M'. n.", is_dprr=True)
        assert result["praenomen"] == "manius"
        assert result["nomen"] == "Aquillius"


class TestTransliterateGreek:
    def test_basic(self):
        assert transliterate_greek("Μάρκος") == "marcus"

    def test_kappa_to_c(self):
        result = transliterate_greek("Κόιντος")
        assert result.startswith("c")  # κ → c

    def test_aquillius(self):
        result = transliterate_greek("Ἀκύλλιος")
        # κυ → cy (υ→y), λλ → ll; result contains "acyll" or "acull"
        assert "acyll" in result or "acull" in result or "aqull" in result

    def test_latin_passthrough(self):
        assert transliterate_greek("P. Cornelius") == "P. Cornelius"

    def test_not_greek(self):
        assert not is_greek("Cornelius Scipio")

    def test_is_greek(self):
        assert is_greek("Κορνήλιος")


class TestParseFiliation:
    def test_father_and_grandfather(self):
        result = parse_filiation("M. f. Cn. n.")
        assert result == {"father": "marcus", "grandfather": "gnaeus"}

    def test_father_only(self):
        result = parse_filiation("L. f.")
        assert result == {"father": "lucius"}

    def test_manius_filiation(self):
        result = parse_filiation("M'. f. M'. n.")
        assert result == {"father": "manius", "grandfather": "manius"}

    def test_no_filiation(self):
        result = parse_filiation("consul designatus")
        assert result == {}

    def test_from_inscription_text(self):
        text = "L. Aquillius M'. f. M'. n. Florus q. restituit"
        result = parse_filiation(text)
        assert result["father"] == "manius"


class TestParseOffice:
    def test_consul(self):
        assert parse_office("M. Aquillius cos.") == "consul"

    def test_praetor(self):
        assert parse_office("C. Sempronius pr.") == "praetor"

    def test_quaestor(self):
        assert parse_office("L. Aquillius q. restituit") == "quaestor"

    def test_tribunus_plebis(self):
        assert parse_office("tr. pl.") == "tribunus plebis"

    def test_proconsul(self):
        assert parse_office("procos.") == "proconsul"

    def test_no_office(self):
        assert parse_office("L. Aquillius Florus") is None
