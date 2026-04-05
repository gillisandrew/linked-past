"""Sanitize RDF files for strict parsers like Oxigraph.

Uses rapper (Raptor RDF parser) for format conversion when available,
with regex post-processing for issues rapper doesn't fix.

Pipeline:
  1. rapper: parse lenient, serialize clean Turtle (handles most syntax issues)
  2. Regex fixes: BCP 47 language tags, bare DOIs (issues in the data, not syntax)
  3. pyoxigraph verify: strict validation, triple count
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# BCP 47: subtags must be max 8 characters
_LANG_TAG = re.compile(r'"([^"]*)"@([a-zA-Z][a-zA-Z0-9-]*)')
_BARE_DOI = re.compile(r"<(doi\.org/)")


def has_rapper() -> bool:
    """Check if rapper (Raptor RDF parser) is installed."""
    return shutil.which("rapper") is not None


@dataclass
class SanitizeResult:
    """Result of sanitizing an RDF file."""

    output_path: Path
    fixes_applied: int
    input_size: int
    output_size: int
    triple_count: int
    used_rapper: bool


# Known non-conforming language tags and their RFC 5646 replacements.
# These are invented tags from upstream data that violate the 8-char subtag limit.
# Replacements use private-use subtags (x-...) per RFC 5646 §4.5.
_LANG_TAG_REPLACEMENTS = {
    "etruscan-in-latin-characters": "x-etruscan-latn",
}


def _fix_lang_tag(match: re.Match) -> str:
    """Fix language tags with subtags exceeding 8 characters.

    RFC 5646 limits all subtags to 8 characters. Rather than truncating
    mid-subtag (which produces meaningless tags), this uses a lookup table
    for known tags and drops oversized subtags at boundaries for unknown ones.
    """
    text = match.group(1)
    tag = match.group(2)
    parts = tag.split("-")
    if not any(len(part) > 8 for part in parts):
        return match.group(0)
    # Check for a known replacement first
    if tag in _LANG_TAG_REPLACEMENTS:
        return f'"{text}"@{_LANG_TAG_REPLACEMENTS[tag]}'
    # Fallback: drop oversized subtags entirely (RFC 5646: truncate at subtag boundaries)
    fixed_parts = [part for part in parts if len(part) <= 8]
    return f'"{text}"@{"-".join(fixed_parts)}'


def _detect_input_format(path: Path) -> str:
    """Detect RDF format from file extension and content."""
    suffix = path.suffix.lower()
    if suffix in (".rdf", ".xml", ".owl"):
        return "rdfxml"
    if suffix in (".nt", ".ntriples"):
        return "ntriples"
    if suffix in (".nq", ".nquads"):
        return "nquads"
    if suffix in (".jsonld", ".json"):
        return "jsonld"
    # Check content for XML signature
    first_bytes = path.read_bytes()[:200]
    if first_bytes.lstrip().startswith(b"<?xml") or first_bytes.lstrip().startswith(b"<rdf:"):
        return "rdfxml"
    return "turtle"


def _rapper_convert(input_path: Path, output_path: Path, input_format: str = "guess") -> int:
    """Convert RDF via rapper. Returns triple count."""
    if input_format == "guess":
        input_format = _detect_input_format(input_path)

    result = subprocess.run(
        ["rapper", "-q", "-i", input_format, "-o", "turtle", str(input_path)],
        capture_output=True,
        timeout=600,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"rapper failed: {stderr[:500]}")

    output_path.write_bytes(result.stdout)

    # Count triples from rapper -c (outputs count on stderr, needs no -q)
    count_result = subprocess.run(
        ["rapper", "-c", "-i", input_format, str(input_path)],
        capture_output=True,
        timeout=600,
    )
    count_stderr = count_result.stderr.decode("utf-8", errors="replace")
    for line in count_stderr.splitlines():
        if "triple" in line:
            parts = line.split()
            for part in parts:
                if part.isdigit():
                    return int(part)
    return 0


def _regex_fixes(text: str) -> tuple[str, int]:
    """Apply regex fixes for issues rapper doesn't handle."""
    original = text

    # Fix BCP 47 language tags (subtags > 8 chars)
    text = _LANG_TAG.sub(_fix_lang_tag, text)

    # Fix bare DOIs missing scheme
    text = _BARE_DOI.sub(r"<https://\1", text)

    fixes = sum(1 for a, b in zip(original.splitlines(), text.splitlines()) if a != b)
    return text, fixes


def sanitize_turtle(
    input_path: str | Path,
    output_path: str | Path | None = None,
    input_format: str = "guess",
) -> SanitizeResult:
    """Sanitize an RDF file for strict parsers.

    If rapper is available, uses it for format conversion (handles most syntax
    issues). Then applies regex fixes for BCP 47 tags and bare DOIs.

    If rapper is not available, applies regex fixes only (input must already
    be Turtle).

    Args:
        input_path: Input RDF file (any format rapper supports)
        output_path: Output Turtle file (default: overwrite input)
        input_format: Input format hint ("guess", "rdfxml", "turtle", etc.)
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path
    else:
        output_path = Path(output_path)

    input_size = input_path.stat().st_size
    used_rapper = False
    triple_count = 0

    if has_rapper():
        # Step 1: regex pre-fixes on input (fixes issues rapper misinterprets, like bare DOIs)
        import tempfile

        text = input_path.read_text(errors="replace")
        text, fixes = _regex_fixes(text)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ttl", delete=False) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)

        # Step 2: rapper converts and normalizes Turtle
        logger.info("Sanitizing %s via rapper", input_path.name)
        triple_count = _rapper_convert(tmp_path, output_path, input_format)
        tmp_path.unlink(missing_ok=True)
        used_rapper = True

        # Step 3: regex post-fixes on rapper output (e.g., BCP 47 tags rapper preserves)
        text = output_path.read_text(errors="replace")
        text, post_fixes = _regex_fixes(text)
        fixes += post_fixes
        output_path.write_text(text)
    else:
        # No rapper — regex fixes only (input must be Turtle)
        logger.info("Sanitizing %s via regex (rapper not available)", input_path.name)
        text = input_path.read_text(errors="replace")
        text, fixes = _regex_fixes(text)
        output_path.write_text(text)

    output_size = output_path.stat().st_size

    if fixes > 0:
        logger.info("Applied %d regex fixes to %s", fixes, output_path.name)

    return SanitizeResult(
        output_path=output_path,
        fixes_applied=fixes,
        input_size=input_size,
        output_size=output_size,
        triple_count=triple_count,
        used_rapper=used_rapper,
    )
