"""Base class and dataclasses for dataset plugins."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path

from pyoxigraph import RdfFormat, Store


@dataclass
class VersionInfo:
    version: str
    source_url: str
    fetched_at: str
    triple_count: int
    rdf_format: str


@dataclass
class ValidationResult:
    valid: bool
    sparql: str
    errors: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class DatasetPlugin:
    """Base class for dataset plugins.

    Subclasses set class attributes (name, display_name, etc.) and inherit
    concrete implementations for context loading, schema rendering, and
    validation.  Only plugins with non-default version info need to override
    ``get_version_info``.
    """

    name: str
    display_name: str
    description: str
    citation: str
    license: str
    url: str
    time_coverage: str
    spatial_coverage: str
    rdf_format: RdfFormat = RdfFormat.TURTLE
    oci_dataset: str = ""
    oci_version: str = "latest"

    # ------------------------------------------------------------------
    # Context directory resolution
    # ------------------------------------------------------------------

    @classmethod
    def _context_dir(cls) -> Path:
        """Return the ``context/`` directory next to the subclass's module."""
        return Path(inspect.getfile(cls)).parent / "context"

    # ------------------------------------------------------------------
    # Initialisation  (loads all YAML context)
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        from linked_past.core.context import load_examples, load_prefixes, load_schemas, load_tips
        from linked_past.core.validate import build_schema_dict, extract_query_classes

        context_dir = self._context_dir()
        if not context_dir.is_dir():
            raise FileNotFoundError(
                f"Context directory not found: {context_dir}. "
                f"Subclasses must live next to a context/ directory."
            )

        self._prefixes = load_prefixes(context_dir)
        self._schemas = load_schemas(context_dir)
        self._hand_written_class_names = set(self._schemas.keys())
        self._examples = load_examples(context_dir)
        self._tips = load_tips(context_dir)
        self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
        for ex in self._examples:
            ex["classes"] = extract_query_classes(ex["sparql"], self._schema_dict)

    # ------------------------------------------------------------------
    # Fetch / load
    # ------------------------------------------------------------------

    def fetch(self, data_dir: Path, force: bool = False) -> Path:
        """Download data via ORAS from OCI registry. Override for custom fetch logic."""
        from linked_past.core.fetch import pull_artifact

        if not self.oci_dataset:
            raise NotImplementedError(f"{self.__class__.__name__} must set oci_dataset or override fetch()")
        return pull_artifact(self.oci_dataset, data_dir, self.oci_version, force=force)

    def load(self, store: Store, rdf_path: Path) -> int:
        """Bulk-load all data files into Oxigraph store, return triple count.

        Loads all .ttl files in rdf_path's directory, skipping _* sidecars
        (e.g. _void.ttl, _schema.yaml). Single-file datasets load just the
        one file; multi-file datasets (like EDH) load all of them.

        After loading, runs RDFS/OWL2 RL materialization to infer triples
        from rdfs:subPropertyOf, rdfs:subClassOf, and other axioms present
        in the data.
        """
        import logging

        from linked_past.core.store import materialize

        load_logger = logging.getLogger(__name__)
        data_dir = rdf_path.parent
        ttl_files = [f for f in sorted(data_dir.glob("*.ttl")) if not f.name.startswith("_")]
        load_logger.info("load dataset=%s files=%d dir=%s", self.name, len(ttl_files), data_dir)
        for ttl in ttl_files:
            store.bulk_load(path=str(ttl), format=self.rdf_format)
            load_logger.info("load dataset=%s loaded=%s triples=%d", self.name, ttl.name, len(store))
        # Load ontology sidecar if present (dataset-specific, e.g. Nomisma for CRRO/OCRE)
        ontology_path = data_dir / "_ontology.ttl"
        if ontology_path.exists():
            store.bulk_load(path=str(ontology_path), format=self.rdf_format)
            load_logger.info("load dataset=%s loaded=_ontology.ttl triples=%d", self.name, len(store))
        # Load bundled standard ontologies (SKOS etc.) for universal inference
        bundled_dir = Path(__file__).resolve().parent.parent / "ontologies"
        if bundled_dir.exists():
            for ont in sorted(bundled_dir.glob("*.ttl")):
                store.bulk_load(path=str(ont), format=self.rdf_format)
                load_logger.info("load dataset=%s loaded=%s triples=%d", self.name, ont.name, len(store))
        try:
            materialize(store)
        except Exception as e:
            load_logger.warning("Materialization failed for %s: %s (continuing without inference)", self.name, e)
        load_logger.info("load dataset=%s complete triples=%d", self.name, len(store))
        return len(store)

    # ------------------------------------------------------------------
    # Prefixes / schema / validation
    # ------------------------------------------------------------------

    def get_prefixes(self) -> dict[str, str]:
        """Return namespace prefix map."""
        return self._prefixes

    def build_schema_dict(self) -> dict:
        """Return dict[class_full_uri][predicate_full_uri] = [range_types]."""
        return self._schema_dict

    def get_schema(self) -> str:
        """Return rendered ontology overview."""
        from linked_past.core.context import (
            get_cross_cutting_tips,
            render_auto_detected_summary,
            render_class_summary,
            render_tips,
        )

        prefix_lines = "\n".join(f"PREFIX {k}: <{v}>" for k, v in self._prefixes.items())
        class_summary = render_class_summary(self._schemas)
        cross_tips = get_cross_cutting_tips(self._tips)
        tips_md = render_tips(cross_tips)
        result = (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )
        auto_section = render_auto_detected_summary(self._schemas, self._hand_written_class_names)
        if auto_section:
            result += f"\n\n{auto_section}"
        return result

    def validate(self, sparql: str) -> ValidationResult:
        """Dataset-specific semantic validation (plugin owns its schema dict)."""
        from linked_past.core.validate import validate_semantics

        class_counts = getattr(self, "_class_counts", None)
        hints = validate_semantics(sparql, self._schema_dict, class_counts=class_counts)
        return ValidationResult(valid=True, sparql=sparql, suggestions=hints)

    def get_relevant_context(self, sparql: str) -> str:
        """Return contextual tips/examples for a SPARQL query."""
        from linked_past.core.context import (
            get_relevant_examples,
            get_relevant_tips,
            render_examples,
            render_tips,
        )
        from linked_past.core.validate import extract_query_classes

        classes = extract_query_classes(sparql, self._schema_dict)
        if not classes:
            return ""
        parts: list[str] = []
        tips = get_relevant_tips(self._tips, classes)
        if tips:
            parts.append(f"## Relevant Tips\n\n{render_tips(tips)}")
        examples = get_relevant_examples(self._examples, classes)
        if examples:
            parts.append(f"## Relevant Examples\n\n{render_examples(examples)}")
        if not parts:
            return ""
        return "\n\n---\n\n" + "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Version / update
    # ------------------------------------------------------------------

    def get_version_info(self, data_dir: Path) -> VersionInfo | None:
        """Return current snapshot metadata, or None if not initialized."""
        return VersionInfo(
            version=self.oci_version,
            source_url=self.url,
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )

    def check_for_updates(self) -> None:
        """Compare local vs upstream. Returns None (not yet implemented)."""
        return None

    # ------------------------------------------------------------------
    # Runtime schema enrichment
    # ------------------------------------------------------------------

    def set_void_class_counts(self, class_counts: dict[str, int]) -> None:
        """Store VoID class counts for validation hints."""
        self._class_counts = class_counts

    def set_auto_schema(self, auto_schema: dict | None) -> None:
        """Merge auto-generated schema classes into this plugin's schemas.

        Called by the registry after loading _schema.yaml from the dataset directory.
        Only adds classes not already in the hand-written schema.
        """
        if not auto_schema or not hasattr(self, "_schemas"):
            return
        from linked_past.core.context import merge_schemas
        from linked_past.core.validate import build_schema_dict

        original_count = len(self._schemas)
        self._schemas = merge_schemas(self._schemas, auto_schema)
        new_count = len(self._schemas) - original_count
        if new_count > 0 and hasattr(self, "_schema_dict") and hasattr(self, "_prefixes"):
            self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
