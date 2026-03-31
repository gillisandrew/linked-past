"""Roman onomastics: name parsing, praenomen normalization, Greek transliteration.

Extracted from scripts/match_dprr_edh.py for shared use across the linked-past package.
"""

from __future__ import annotations

import re
import unicodedata

# ── Praenomen maps ──

PRAENOMEN_MAP: dict[str, str] = {
    "c.": "gaius", "c": "gaius",
    "cn.": "gnaeus", "cn": "gnaeus",
    "l.": "lucius", "l": "lucius",
    "m.": "marcus", "m": "marcus",
    "m'.": "manius", "mn.": "manius", "mn": "manius",
    "p.": "publius", "p": "publius",
    "q.": "quintus", "q": "quintus",
    "sex.": "sextus", "sex": "sextus",
    "ser.": "servius", "ser": "servius",
    "sp.": "spurius", "sp": "spurius",
    "t.": "titus", "t": "titus",
    "ti.": "tiberius", "ti": "tiberius",
    "a.": "aulus", "a": "aulus",
    "d.": "decimus", "d": "decimus",
    "n.": "numerius",
    "ap.": "appius", "ap": "appius",
    # Greek equivalents
    "γ.": "gaius", "γάιος": "gaius", "γαίου": "gaius",
    "γν.": "gnaeus", "γναῖος": "gnaeus",
    "λ.": "lucius", "λεύκιος": "lucius", "λευκίου": "lucius",
    "μ.": "marcus", "μάρκος": "marcus", "μάρκου": "marcus",
    "μάνιος": "manius", "μανίου": "manius",
    "π.": "publius", "πόπλιος": "publius",
    "κ.": "quintus", "κόιντος": "quintus",
    "τ.": "titus", "τίτος": "titus",
    "σέξτος": "sextus",
    "τιβέριος": "tiberius",
}

# Greek praenomen full forms → canonical Latin
GREEK_PRAENOMINA: dict[str, str] = {
    "γαιος": "gaius", "γάιος": "gaius", "γαίου": "gaius",
    "γναιος": "gnaeus", "γναῖος": "gnaeus",
    "λευκιος": "lucius", "λεύκιος": "lucius", "λευκίου": "lucius",
    "μαρκος": "marcus", "μάρκος": "marcus", "μάρκου": "marcus",
    "μανιος": "manius", "μάνιος": "manius", "μανίου": "manius",
    "ποπλιος": "publius", "πόπλιος": "publius",
    "κοιντος": "quintus", "κόιντος": "quintus",
    "τιτος": "titus", "τίτος": "titus",
    "σεξτος": "sextus", "σέξτος": "sextus",
    "τιβεριος": "tiberius", "τιβέριος": "tiberius",
    "αυλος": "aulus", "αὖλος": "aulus",
    "δεκιμος": "decimus", "δέκιμος": "decimus",
    "αππιος": "appius", "ἄππιος": "appius",
    "σερουιος": "servius", "σερούιος": "servius",
    "σπουριος": "spurius", "σπούριος": "spurius",
}


# ── Greek → Latin transliteration tables ──

# Multi-character digraphs (order matters — longer sequences first)
_GREEK_DIGRAPHS: list[tuple[str, str]] = [
    # Diphthongs and clusters
    ("αι", "ae"), ("ει", "ei"), ("οι", "oe"), ("ου", "u"),
    ("αυ", "au"), ("ευ", "eu"), ("ηυ", "eu"),
    ("γγ", "ng"), ("γκ", "nc"), ("γξ", "nx"), ("γχ", "nch"),
    ("μπ", "mp"), ("ντ", "nt"),
    # Aspirates
    ("θ", "th"), ("φ", "ph"), ("χ", "ch"), ("ψ", "ps"),
    # Double letters
    ("λλ", "ll"), ("σσ", "ss"), ("ρρ", "rrh"),
]

# Single character map (after digraphs are handled)
_GREEK_SINGLE: dict[str, str] = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e",
    "ζ": "z", "η": "e", "ι": "i", "κ": "c", "λ": "l",
    "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p",
    "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y",
    "ω": "o",
    # Archaic/rare
    "ϝ": "v", "ϛ": "st", "ϙ": "q",
}

# Common Greek→Latin name endings
_GREEK_ENDINGS: list[tuple[str, str]] = [
    (r"ios$", "ius"),      # Ἀκύλλιος → Aquillius
    (r"ion$", "ium"),      # Βρεντέσιον → Brundisium
    (r"os$", "us"),        # Μάρκος → Marcus
    (r"on$", "um"),        # (neuter)
    (r"e$", "a"),          # (first decl. Greek → Latin)
    (r"ou$", "i"),         # genitive: Μανίου → Manii
    (r"oi$", "i"),         # nominative plural
]


def strip_accents(s: str) -> str:
    """Remove combining diacritical marks (accents, breathing) from Greek text."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def is_greek(text: str) -> bool:
    """Check if text contains Greek characters."""
    return any("\u0370" <= c <= "\u03FF" or "\u1F00" <= c <= "\u1FFF" for c in text)


def transliterate_greek(text: str) -> str:
    """Transliterate Greek text to Latin equivalent for Roman name matching.

    Handles: diphthongs, aspirates, standard letter mappings, and
    common Greek→Latin name ending conversions (-ιος→-ius, -ος→-us).
    """
    if not is_greek(text):
        return text

    # Normalize and strip accents/breathing marks
    result = strip_accents(text.lower())

    # Apply digraph replacements (longest first)
    for greek, latin in _GREEK_DIGRAPHS:
        result = result.replace(greek, latin)

    # Apply single character replacements
    chars = []
    for c in result:
        chars.append(_GREEK_SINGLE.get(c, c))
    result = "".join(chars)

    # Apply Latin name ending corrections
    words = result.split()
    for i, word in enumerate(words):
        for pattern, replacement in _GREEK_ENDINGS:
            new_word = re.sub(pattern, replacement, word)
            if new_word != word:
                words[i] = new_word
                break
    result = " ".join(words)

    return result


def normalize_praenomen(token: str) -> str | None:
    """Normalize a praenomen token (Latin or Greek) to canonical lowercase form."""
    token_lower = token.lower().rstrip(".")
    token_with_dot = token.lower()
    # Try Latin map
    result = PRAENOMEN_MAP.get(token_with_dot) or PRAENOMEN_MAP.get(token_lower)
    if result:
        return result
    # Try Greek map (strip accents first)
    stripped = strip_accents(token_lower)
    return GREEK_PRAENOMINA.get(stripped) or GREEK_PRAENOMINA.get(token_lower)


def parse_roman_name(name: str, is_dprr: bool = False) -> dict:
    """Parse a Roman name string into praenomen, nomen, cognomen components.

    Parameters
    ----------
    name:
        Raw name string (Latin or transliterated Greek).
    is_dprr:
        If True, strip leading DPRR identifier (e.g. "AQUI1614 M'. Aquillius …").
    """
    # Remove question marks, brackets
    clean = re.sub(r"[?\[\]]", "", name).strip()

    # Strip DPRR identifier token (e.g. "AQUI1614")
    if is_dprr:
        clean = re.sub(r"^[A-Z]+\d+\s+", "", clean)

    # Strip parenthetical disambiguation numbers like "(10)"
    clean = re.sub(r"\(\d+\)", "", clean).strip()

    parts = clean.split()
    if not parts:
        return {}

    result: dict = {}

    # Try to identify praenomen
    first_lower = parts[0].lower().rstrip(".")
    first_with_dot = parts[0].lower()
    prae = PRAENOMEN_MAP.get(first_with_dot) or PRAENOMEN_MAP.get(first_lower)
    if prae:
        result["praenomen"] = prae
        parts = parts[1:]

    if not parts:
        return result

    # Next part is typically nomen (gens name, ending in -ius/-ia)
    result["nomen"] = parts[0].rstrip(".,;")

    # Remaining parts are cognomen(s), skip filiation like "f.", "n."
    cognomina = []
    skip_next = False
    for i, p in enumerate(parts[1:], 1):
        p_clean = p.rstrip(".,;")
        if skip_next:
            skip_next = False
            continue
        if p_clean.lower() in ("f", "n", "fil", "filius", "nepos"):
            continue
        if len(p_clean) <= 2 and p_clean[0].isupper():
            # Likely abbreviation like tribe or filiation
            skip_next = True
            continue
        if p_clean and p_clean[0].isupper():
            cognomina.append(p_clean)

    if cognomina:
        result["cognomen"] = cognomina[0]
        if len(cognomina) > 1:
            result["cognomina_extra"] = cognomina[1:]

    return result


def parse_filiation(text: str) -> dict[str, str]:
    """Extract filiation from inscription text. Returns {father: praenomen, grandfather: praenomen}."""
    result: dict[str, str] = {}
    # Match "X." or "X'." praenomen abbreviations before f. (father) and n. (grandfather)
    # Handles M'. (manius), M. (marcus), L. (lucius) etc.
    father_match = re.search(r"([\w']+)\.?\s*f\.", text)
    if father_match:
        token = father_match.group(1)
        prae = normalize_praenomen(token + ".")
        if prae:
            result["father"] = prae
    # Match "X. n." for grandfather
    grandfather_match = re.search(r"([\w']+)\.?\s*n\.", text)
    if grandfather_match:
        token = grandfather_match.group(1)
        prae = normalize_praenomen(token + ".")
        if prae:
            result["grandfather"] = prae
    return result


def parse_office(text: str) -> str | None:
    """Extract the highest office mentioned in inscription text."""
    patterns = [
        (r"\bcos\b\.?", "consul"),
        (r"\bprocos\b\.?", "proconsul"),
        (r"\bpr\b\.(?!\s*q)", "praetor"),  # pr. but not pr. q. (proquaestor)
        (r"\btr\.\s*pl\b\.?", "tribunus plebis"),
        (r"\baed\b\.?", "aedilis"),
        (r"(?<!\w)q\.\s*(?:restituit|designat|pro\b|urbana)", "quaestor"),  # q. followed by role context
        (r"\bquaestor\b", "quaestor"),  # full word
        (r"\bleg\b\.?", "legatus"),
        (r"\bpropr\b\.?", "propraetor"),
    ]
    for pattern, office in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return office
    return None


def normalize_edh_name(name: str) -> tuple[str, bool]:
    """Normalize an EDH person name. Returns (normalized_name, was_greek).

    If the name is Greek, transliterates to Latin form first.
    Also handles EDH conventions like "(= Plautius)" annotations.
    """
    was_greek = is_greek(name)

    if was_greek:
        name = transliterate_greek(name)

    # Remove EDH annotations like "(= Plautius)"
    name = re.sub(r"\(=\s*\w+\)", "", name)
    # Remove question marks but keep brackets info
    name = re.sub(r"\?", "", name)

    return name.strip(), was_greek
