"""Local Oxigraph store helpers: open, load, query."""

from __future__ import annotations

import logging
from pathlib import Path

from pyoxigraph import Literal, RdfFormat, Store

logger = logging.getLogger(__name__)

# Default XDG data directory
_DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "linked-past"


def get_data_dir() -> Path:
    import os

    raw = os.environ.get("LINKED_PAST_DATA_DIR")
    if raw:
        return Path(raw)
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "linked-past"
    return _DEFAULT_DATA_DIR


def create_store(store_path: Path) -> Store:
    store_path.mkdir(parents=True, exist_ok=True)
    return Store(str(store_path))


def get_read_only_store(store_path: Path) -> Store:
    return Store.read_only(str(store_path))


def is_initialized(store_path: Path) -> bool:
    return store_path.exists() and any(store_path.iterdir())


def load_rdf(store: Store, file_path: Path, rdf_format: RdfFormat = RdfFormat.TURTLE) -> int:
    """Bulk-load an RDF file into the store. Returns the triple count after loading."""
    store.bulk_load(path=str(file_path), format=rdf_format)
    return len(store)


# Preferred languages for literal selection, in priority order.
DEFAULT_LANG_PREFS = ("en", "")


def execute_ask(store: Store, sparql: str) -> bool:
    """Execute a SPARQL ASK query and return True/False."""
    import re

    # Strip PREFIX declarations to find the query form
    body = re.sub(r"PREFIX\s+\S+\s*<[^>]*>\s*", "", sparql, flags=re.IGNORECASE).strip()
    if not body.upper().startswith("ASK"):
        raise ValueError("Expected ASK query, got: " + sparql[:40])
    return bool(store.query(sparql))


def execute_query(
    store: Store,
    sparql: str,
    prefix_map: dict[str, str] | None = None,
    lang_prefs: tuple[str, ...] | None = None,
) -> list[dict[str, str]]:
    """Execute a SPARQL SELECT query and return results as a list of dicts.

    If prefix_map is provided, URIs in results are compressed to prefixed form
    (e.g., http://nomisma.org/id/denarius → nm:denarius).

    If lang_prefs is provided (e.g., ("en", "")), language-tagged literals are
    filtered: for each variable, only the best-matching language is kept when
    multiple rows differ only by language tag. The default is None (no filtering).
    Pass DEFAULT_LANG_PREFS for English-preferred behavior.
    """
    results = store.query(sparql)
    if not hasattr(results, "variables"):
        raise ValueError(
            "Only SELECT queries are supported. "
            "CONSTRUCT, ASK, and DESCRIBE queries are not implemented."
        )
    # Build reverse prefix map for compression: namespace → prefix
    compress = None
    if prefix_map:
        # Sort by namespace length descending so longer prefixes match first
        compress = sorted(
            ((ns, prefix) for prefix, ns in prefix_map.items()),
            key=lambda x: len(x[0]),
            reverse=True,
        )

    variables = [v.value for v in results.variables]
    rows = []
    for solution in results:
        row: dict[str, str | None] = {}
        row_langs: dict[str, str | None] = {}  # var_name → language tag
        for var_name in variables:
            value = solution[var_name]
            if value is None:
                row[var_name] = None
                row_langs[var_name] = None
            else:
                val_str = value.value
                # Preserve language tag info for filtering
                lang = value.language if isinstance(value, Literal) else None
                row_langs[var_name] = lang
                if compress and val_str.startswith("http"):
                    for ns, prefix in compress:
                        if val_str.startswith(ns):
                            val_str = f"{prefix}:{val_str[len(ns):]}"
                            break
                row[var_name] = val_str
        row["_langs"] = row_langs  # type: ignore[assignment]
        rows.append(row)

    # Language preference filtering
    if lang_prefs and rows:
        rows = _filter_by_lang_prefs(rows, variables, lang_prefs)

    # Strip internal _langs metadata before returning
    for row in rows:
        row.pop("_langs", None)

    return rows


def _filter_by_lang_prefs(
    rows: list[dict],
    variables: list[str],
    lang_prefs: tuple[str, ...],
) -> list[dict]:
    """Filter rows to keep only the best language match per unique key.

    Groups rows by non-literal key columns, then for each group picks
    the row whose language tags best match the preference order.
    """
    if not rows:
        return rows

    # Find which variables have language-tagged values
    lang_vars = set()
    for row in rows:
        langs = row.get("_langs", {})
        for var in variables:
            if langs.get(var) is not None:
                lang_vars.add(var)

    if not lang_vars:
        return rows  # No language-tagged values, nothing to filter

    # Build a priority map: language → score (lower is better)
    lang_priority = {lang: i for i, lang in enumerate(lang_prefs)}
    worst = len(lang_prefs)

    def row_score(row: dict) -> int:
        """Score a row by how well its language tags match preferences."""
        langs = row.get("_langs", {})
        total = 0
        for var in lang_vars:
            lang = langs.get(var)
            # Normalize: None and "" both mean "no language tag"
            lang_key = lang if lang else ""
            total += lang_priority.get(lang_key, worst)
        return total

    # Group by non-lang-varying key (all variables except the tagged ones)
    key_vars = [v for v in variables if v not in lang_vars]
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = tuple(row.get(v) for v in key_vars) if key_vars else ("_all",)
        groups.setdefault(key, []).append(row)

    # Pick the best row per group
    result = []
    for group_rows in groups.values():
        best = min(group_rows, key=row_score)
        result.append(best)

    return result
