"""Base class and dataclasses for dataset plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
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
class UpdateInfo:
    current: str
    available: str
    changelog_url: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    sparql: str
    errors: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class DatasetPlugin(ABC):
    """Abstract base class for dataset plugins.

    Subclasses must set class attributes and implement all abstract methods.
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

    def fetch(self, data_dir: Path) -> Path:
        """Download data via ORAS from OCI registry. Override for custom fetch logic."""
        from linked_past.core.fetch import pull_artifact

        if not self.oci_dataset:
            raise NotImplementedError(f"{self.__class__.__name__} must set oci_dataset or override fetch()")
        return pull_artifact(self.oci_dataset, data_dir, self.oci_version)

    def load(self, store: Store, rdf_path: Path) -> int:
        """Bulk-load all data files into Oxigraph store, return triple count.

        Loads all .ttl files in rdf_path's directory, skipping _* sidecars
        (e.g. _void.ttl, _schema.yaml). Single-file datasets load just the
        one file; multi-file datasets (like EDH) load all of them.
        """
        data_dir = rdf_path.parent
        ttl_files = [f for f in sorted(data_dir.glob("*.ttl")) if not f.name.startswith("_")]
        for ttl in ttl_files:
            store.bulk_load(path=str(ttl), format=self.rdf_format)
        return len(store)

    @abstractmethod
    def get_prefixes(self) -> dict[str, str]:
        """Return namespace prefix map."""

    @abstractmethod
    def get_schema(self) -> str:
        """Return rendered ontology overview."""

    @abstractmethod
    def build_schema_dict(self) -> dict:
        """Return dict[class_full_uri][predicate_full_uri] = [range_types]."""

    @abstractmethod
    def validate(self, sparql: str) -> ValidationResult:
        """Dataset-specific semantic validation (plugin owns its schema dict)."""

    def get_relevant_context(self, sparql: str) -> str:
        """Return contextual tips/examples for a SPARQL query. Default: empty."""
        return ""

    @abstractmethod
    def get_version_info(self, data_dir: Path) -> VersionInfo | None:
        """Return current snapshot metadata, or None if not initialized."""

    def check_for_updates(self) -> UpdateInfo | None:
        """Compare local vs upstream. Returns None if up to date."""
        return None

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
