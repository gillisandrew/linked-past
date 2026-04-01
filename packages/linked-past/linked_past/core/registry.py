"""Dataset registry: discovers plugins, manages store lifecycle."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from pyoxigraph import Store

from linked_past.core.store import create_store, get_read_only_store, is_initialized
from linked_past.datasets.base import DatasetPlugin

logger = logging.getLogger(__name__)


class DatasetRegistry:
    """Manages dataset plugins and their Oxigraph stores."""

    _URI_NAMESPACES: dict[str, str] = {
        "http://romanrepublic.ac.uk/rdf/": "dprr",
        "https://pleiades.stoa.org/places/": "pleiades",
        "http://n2t.net/ark:/99152/": "periodo",
        "http://nomisma.org/id/": "nomisma",
        "http://numismatics.org/crro/id/": "crro",
        "http://numismatics.org/ocre/id/": "ocre",
        "http://edh-www.adw.uni-heidelberg.de/edh/": "edh",
        "https://edh-www.adw.uni-heidelberg.de/edh/": "edh",
    }

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._plugins: dict[str, DatasetPlugin] = {}
        self._stores: dict[str, Store] = {}
        self._metadata: dict[str, dict] = {}

    def register(self, plugin: DatasetPlugin) -> None:
        self._plugins[plugin.name] = plugin

    def list_datasets(self) -> list[str]:
        return list(self._plugins.keys())

    def get_plugin(self, name: str) -> DatasetPlugin:
        if name not in self._plugins:
            raise KeyError(f"Unknown dataset: {name!r}. Available: {', '.join(self._plugins)}")
        return self._plugins[name]

    def get_store(self, name: str) -> Store:
        if name not in self._stores:
            raise KeyError(f"Dataset {name!r} is not initialized.")
        return self._stores[name]

    def get_metadata(self, name: str) -> dict:
        return self._metadata.get(name, {})

    def dataset_for_uri(self, uri: str) -> str | None:
        """Determine which dataset a URI belongs to based on namespace."""
        for ns, name in self._URI_NAMESPACES.items():
            if uri.startswith(ns) and name in self._plugins:
                return name
        return None

    def initialize_dataset(self, name: str) -> None:
        plugin = self.get_plugin(name)
        dataset_dir = self._data_dir / name
        store_path = dataset_dir / "store"

        if is_initialized(store_path):
            logger.info("Dataset %s already initialized, opening read-only", name)
            self._stores[name] = get_read_only_store(store_path)
            # Load cached metadata from registry.json
            registry_path = self._data_dir / "registry.json"
            if registry_path.exists():
                data = json.loads(registry_path.read_text())
                if name in data:
                    self._metadata[name] = data[name]
            self._load_void(name, dataset_dir)
            self._load_schema(name, dataset_dir)
            return

        dataset_dir.mkdir(parents=True, exist_ok=True)
        rdf_path = plugin.fetch(dataset_dir)

        store = create_store(store_path)
        try:
            triple_count = plugin.load(store, rdf_path)
        except Exception:
            del store
            shutil.rmtree(store_path, ignore_errors=True)
            raise
        del store  # noqa: F821
        logger.info("Loaded %d triples for dataset %s", triple_count, name)

        self._stores[name] = get_read_only_store(store_path)
        self._save_registry(name, plugin, dataset_dir, triple_count)
        self._load_void(name, dataset_dir)
        self._load_schema(name, dataset_dir)

    def initialize_all(self) -> None:
        """Initialize all registered datasets (may download data)."""
        for name in self._plugins:
            try:
                self.initialize_dataset(name)
            except Exception as e:
                logger.warning("Failed to initialize dataset %s: %s (skipping)", name, e)

    def initialize_cached(self) -> None:
        """Initialize only datasets that already have local stores (no downloads)."""
        for name in self._plugins:
            dataset_dir = self._data_dir / name
            store_path = dataset_dir / "store"
            if is_initialized(store_path):
                try:
                    self.initialize_dataset(name)
                except Exception as e:
                    logger.warning("Failed to open cached dataset %s: %s", name, e)

    def _load_void(self, name: str, dataset_dir: Path) -> None:
        """Load VoID description from dataset directory if present."""
        void_path = dataset_dir / "_void.ttl"
        if not void_path.exists():
            return
        try:
            from pyoxigraph import RdfFormat
            from pyoxigraph import Store as VoidStore

            vs = VoidStore()
            vs.bulk_load(path=str(void_path), format=RdfFormat.TURTLE)
            void_meta: dict = {}
            # Extract key VoID stats via SPARQL
            for row in vs.query(
                "PREFIX void: <http://rdfs.org/ns/void#> "
                "SELECT ?p ?o WHERE { ?s a void:Dataset ; ?p ?o }"
            ):
                pred = str(row[0]).strip("<>").rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                obj = row[1]
                try:
                    void_meta[pred] = obj.value
                except AttributeError:
                    void_meta[pred] = str(obj).strip("<>")

            # Extract class partitions
            partitions = []
            for row in vs.query(
                "PREFIX void: <http://rdfs.org/ns/void#> "
                "SELECT ?class ?entities WHERE { "
                "  ?s void:classPartition [ void:class ?class ; void:entities ?entities ] "
                "}"
            ):
                partitions.append({
                    "class": str(row[0]).strip("<>"),
                    "entities": row[1].value,
                })
            if partitions:
                void_meta["classPartitions"] = partitions

            if void_meta:
                meta = self._metadata.setdefault(name, {})
                meta["void"] = void_meta
                # Pass class counts to plugin for validation hints
                plugin = self._plugins.get(name)
                if plugin and "classPartitions" in void_meta:
                    counts = {cp["class"]: int(cp["entities"]) for cp in void_meta["classPartitions"]}
                    plugin.set_void_class_counts(counts)
                logger.info("Loaded VoID for %s: %s triples, %s classes",
                            name, void_meta.get("triples", "?"), void_meta.get("classes", "?"))
            del vs
        except Exception as e:
            logger.debug("Could not load VoID for %s: %s", name, e)

    def _load_schema(self, name: str, dataset_dir: Path) -> None:
        """Load auto-generated schema from dataset directory if present."""
        schema_path = dataset_dir / "_schema.yaml"
        if not schema_path.exists():
            return
        try:
            import yaml

            with open(schema_path) as f:
                data = yaml.safe_load(f)
            classes = data.get("classes", {})
            if classes:
                meta = self._metadata.setdefault(name, {})
                meta["auto_schema"] = classes
                # Merge into plugin's live schema
                plugin = self._plugins.get(name)
                if plugin:
                    plugin.set_auto_schema(classes)
                logger.info("Loaded auto-generated schema for %s: %d classes", name, len(classes))
        except Exception as e:
            logger.debug("Could not load schema for %s: %s", name, e)

    def _save_registry(self, name: str, plugin: DatasetPlugin, dataset_dir: Path, triple_count: int) -> None:
        version_info = plugin.get_version_info(dataset_dir)
        if not version_info:
            logger.warning("No version info for %s; registry not updated", name)
            return

        registry_path = self._data_dir / "registry.json"
        if registry_path.exists():
            data = json.loads(registry_path.read_text())
        else:
            data = {}

        entry = {
            "version": version_info.version,
            "source_url": version_info.source_url,
            "fetched_at": version_info.fetched_at,
            "triple_count": triple_count,
            "rdf_format": version_info.rdf_format,
            "license": plugin.license,
        }
        data[name] = entry
        self._metadata[name] = entry

        registry_path.write_text(json.dumps(data, indent=2))
