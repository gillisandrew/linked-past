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

    @abstractmethod
    def fetch(self, data_dir: Path) -> Path:
        """Download data, return path to RDF file(s)."""

    def load(self, store: Store, rdf_path: Path) -> int:
        """Bulk-load into Oxigraph store, return triple count.

        Default implementation uses self.rdf_format. Override for custom loading.
        """
        store.bulk_load(path=str(rdf_path), format=self.rdf_format)
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
