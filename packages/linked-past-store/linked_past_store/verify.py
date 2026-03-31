"""Verify RDF files load cleanly into Oxigraph."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pyoxigraph import RdfFormat, Store

logger = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    """Result of verifying an RDF file."""

    path: Path
    triple_count: int
    format: str
    errors: list[str]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def detect_format(path: Path) -> RdfFormat:
    """Auto-detect RDF format from file content."""
    first_bytes = path.read_bytes()[:200]
    if first_bytes.lstrip().startswith(b"<?xml") or first_bytes.lstrip().startswith(b"<rdf:"):
        return RdfFormat.RDF_XML
    return RdfFormat.TURTLE


def verify_turtle(path: str | Path) -> VerifyResult:
    """Verify an RDF file loads cleanly into Oxigraph.

    Returns a VerifyResult with triple count and any errors.
    """
    path = Path(path)
    fmt = detect_format(path)
    errors = []

    try:
        store = Store()
        store.bulk_load(path=str(path), format=fmt)
        triple_count = len(store)
        del store
    except Exception as e:
        errors.append(str(e))
        triple_count = 0

    fmt_name = "rdf/xml" if fmt == RdfFormat.RDF_XML else "turtle"
    if errors:
        logger.error("Verification failed for %s: %s", path.name, errors[0])
    else:
        logger.info("Verified %s: %d triples (%s)", path.name, triple_count, fmt_name)

    return VerifyResult(
        path=path,
        triple_count=triple_count,
        format=fmt_name,
        errors=errors,
    )
