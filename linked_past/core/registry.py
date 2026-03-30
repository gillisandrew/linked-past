"""Dataset registry: discovers plugins, manages store lifecycle."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pyoxigraph import Store

from linked_past.core.store import create_store, get_read_only_store, is_initialized
from linked_past.datasets.base import DatasetPlugin

logger = logging.getLogger(__name__)


class DatasetRegistry:
    """Manages dataset plugins and their Oxigraph stores."""

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

    def initialize_dataset(self, name: str) -> None:
        plugin = self.get_plugin(name)
        dataset_dir = self._data_dir / name
        store_path = dataset_dir / "store"

        if is_initialized(store_path):
            logger.info("Dataset %s already initialized, opening read-only", name)
            self._stores[name] = get_read_only_store(store_path)
            return

        dataset_dir.mkdir(parents=True, exist_ok=True)
        rdf_path = plugin.fetch(dataset_dir)

        store = create_store(store_path)
        try:
            triple_count = plugin.load(store, rdf_path)
        except Exception:
            del store
            import shutil
            shutil.rmtree(store_path, ignore_errors=True)
            raise
        del store  # noqa: F821
        logger.info("Loaded %d triples for dataset %s", triple_count, name)

        self._stores[name] = get_read_only_store(store_path)
        self._save_registry(name, plugin, dataset_dir, triple_count)

    def initialize_all(self) -> None:
        for name in self._plugins:
            self.initialize_dataset(name)

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
