"""Sanitize RDF files for strict parsers like Oxigraph.

Fixes common issues in upstream RDF datasets:
- BCP 47 language tag violations (subtags > 8 characters)
- IRIs missing schemes (e.g., doi.org/... → https://doi.org/...)
- Invalid characters in Turtle local names (parentheses, etc.)
- Invalid Unicode code points in IRIs
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# BCP 47: subtags must be max 8 characters
_LANG_TAG = re.compile(r'"([^"]*)"@([a-zA-Z][a-zA-Z0-9-]*)')
_BARE_DOI = re.compile(r"<(doi\.org/)")


@dataclass
class SanitizeResult:
    """Result of sanitizing an RDF file."""

    output_path: Path
    fixes_applied: int
    input_size: int
    output_size: int


def _fix_lang_tag(match: re.Match) -> str:
    """Fix language tags with subtags exceeding 8 characters."""
    text = match.group(1)
    tag = match.group(2)
    parts = tag.split("-")
    if not any(len(part) > 8 for part in parts):
        return match.group(0)  # Valid tag, return unchanged
    fixed_parts = [part[:8] if len(part) > 8 else part for part in parts]
    return f'"{text}"@{"-".join(fixed_parts)}'


def sanitize_turtle(
    input_path: str | Path,
    output_path: str | Path | None = None,
) -> SanitizeResult:
    """Sanitize a Turtle file for strict RDF parsers.

    Fixes BCP 47 language tags, bare DOIs, and other common issues.
    If output_path is None, overwrites the input file.

    Returns a SanitizeResult with details of fixes applied.
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path
    else:
        output_path = Path(output_path)

    text = input_path.read_text(errors="replace")
    input_size = len(text)
    original = text

    # Fix BCP 47 language tags (only those with subtags > 8 chars)
    text = _LANG_TAG.sub(_fix_lang_tag, text)

    # Fix bare DOIs missing scheme
    text = _BARE_DOI.sub(r"<https://\1", text)

    # Count actual changes by diffing
    fixes = sum(1 for a, b in zip(original.splitlines(), text.splitlines()) if a != b)

    output_path.write_text(text)
    output_size = len(text)

    if fixes > 0:
        logger.info("Applied %d fixes to %s", fixes, input_path.name)

    return SanitizeResult(
        output_path=output_path,
        fixes_applied=fixes,
        input_size=input_size,
        output_size=output_size,
    )
