"""Local Oxigraph store helpers: open, load, query."""

from __future__ import annotations

from pathlib import Path

from pyoxigraph import Literal, RdfFormat, Store

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


def materialize(store: Store) -> int:
    """Run RDFS/OWL2 RL forward-chaining and insert inferred triples.

    Uses the `reasonable` library (Rust Datalog engine) to compute the
    deductive closure. Returns the number of genuinely new triples added.

    Fast no-op when the data contains no RDFS/OWL axioms.
    """
    import logging
    import tempfile

    import reasonable
    from pyoxigraph import BlankNode, NamedNode, Quad, RdfFormat, serialize

    logger = logging.getLogger(__name__)

    import time

    # Quick check: skip if no RDFS/OWL axioms present
    has_axioms = bool(store.query(
        "ASK { "
        "  { ?p <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> ?q } "
        "  UNION "
        "  { ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?d } "
        "}"
    ))
    if not has_axioms:
        logger.info("materialize: no RDFS/OWL axioms found, skipping")
        return 0

    t0 = time.monotonic()
    store_size = len(store)
    logger.info("materialize: starting (store has %d triples)", store_size)

    # Collect predicates and classes involved in RDFS axiom chains.
    # Only serialize triples relevant to inference — avoids loading the
    # entire store into the reasoner (which OOMs on large datasets like EDH).
    axiom_rows = list(store.query(
        "SELECT ?sub ?super ?type WHERE { "
        "  { ?sub <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> ?super . BIND('prop' AS ?type) } "
        "  UNION "
        "  { ?sub <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?super . BIND('class' AS ?type) } "
        "}"
    ))

    sub_props = set()
    sub_classes = set()
    for row in axiom_rows:
        sub_uri = str(row[0]).strip("<>")
        super_uri = str(row[1]).strip("<>")
        if row[2].value == "prop":
            sub_props.add(sub_uri)
            sub_props.add(super_uri)
        else:
            sub_classes.add(sub_uri)
            sub_classes.add(super_uri)

    logger.info(
        "materialize: found %d axioms (%d sub-properties, %d sub-classes)",
        len(axiom_rows), len(sub_props), len(sub_classes),
    )

    # Build CONSTRUCT that extracts only inference-relevant triples:
    # 1. The axiom triples themselves (subPropertyOf, subClassOf)
    # 2. Instance triples using sub-properties (e.g., ?s skos:prefLabel ?o)
    # 3. Type triples for sub-classes (e.g., ?s a nmo:Hoard)
    _RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
    _SUB_PROP = "<http://www.w3.org/2000/01/rdf-schema#subPropertyOf>"
    _SUB_CLASS = "<http://www.w3.org/2000/01/rdf-schema#subClassOf>"
    parts = [
        f"{{ ?s ?p ?o . FILTER(?p = {_SUB_PROP} || ?p = {_SUB_CLASS}) }}",
    ]
    if sub_props:
        prop_values = " ".join(f"<{p}>" for p in sub_props)
        parts.append(f"{{ ?s ?p ?o . VALUES ?p {{ {prop_values} }} }}")
    if sub_classes:
        class_values = " ".join(f"<{c}>" for c in sub_classes)
        parts.append(
            f"{{ ?s {_RDF_TYPE} ?o . VALUES ?o {{ {class_values} }} . BIND({_RDF_TYPE} AS ?p) }}"
        )

    construct_sparql = "CONSTRUCT { ?s ?p ?o } WHERE { " + " UNION ".join(parts) + " }"

    tmp = tempfile.NamedTemporaryFile(suffix=".ttl", delete=False)
    try:
        quads = store.query(construct_sparql)
        with open(tmp.name, "wb") as f:
            serialize(quads, f, format=RdfFormat.TURTLE)

        tmp_size = Path(tmp.name).stat().st_size
        logger.info(
            "materialize: serialized %s relevant triples to temp file (%d KB) in %.1fs",
            f"{tmp_size // 1024:,}", tmp_size // 1024,
            time.monotonic() - t0,
        )

        t1 = time.monotonic()
        r = reasonable.PyReasoner()
        r.load_file(tmp.name)
        inferred = r.reason()
        logger.info(
            "materialize: reasoner produced %d triples in %.1fs",
            len(inferred), time.monotonic() - t1,
        )
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    # Insert genuinely new triples — preserve language tags and datatypes
    def _to_term(val):
        # reasonable returns rdflib terms — convert to pyoxigraph equivalents
        from rdflib.term import BNode as RdflibBNode
        from rdflib.term import Literal as RdflibLiteral
        from rdflib.term import URIRef as RdflibURIRef

        if isinstance(val, RdflibURIRef):
            return NamedNode(str(val))
        if isinstance(val, RdflibBNode):
            return BlankNode(str(val))
        if isinstance(val, RdflibLiteral):
            if val.language:
                return Literal(str(val), language=val.language)
            if val.datatype:
                return Literal(str(val), datatype=NamedNode(str(val.datatype)))
            return Literal(str(val))
        # Fallback for plain strings
        val_str = str(val)
        if val_str.startswith("http://") or val_str.startswith("https://"):
            return NamedNode(val_str)
        if val_str.startswith("_:"):
            return BlankNode(val_str[2:])
        return Literal(val_str)

    added = 0
    for s, p, o in inferred:
        try:
            subj = _to_term(s)
            pred = NamedNode(str(p))
            obj = _to_term(o)
            existing = list(store.quads_for_pattern(subj, pred, obj, None))
            if not existing:
                store.add(Quad(subj, pred, obj))
                added += 1
        except Exception:
            pass  # Skip malformed triples (e.g., literals in subject position)

    elapsed = time.monotonic() - t0
    logger.info(
        "materialize: added %d new triples (%d from reasoner, %d duplicates skipped) in %.1fs",
        added, len(inferred), len(inferred) - added, elapsed,
    )
    return added


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
