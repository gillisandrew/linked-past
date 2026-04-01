"""Generic Oxigraph store management for any RDF dataset."""

import os
from pathlib import Path

from pyoxigraph import RdfFormat, Store


def get_data_dir() -> Path:
    """Compute the linked-past data directory.

    Precedence: LINKED_PAST_DATA_DIR > XDG_DATA_HOME/linked-past > ~/.local/share/linked-past
    """
    explicit = os.environ.get("LINKED_PAST_DATA_DIR")
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "linked-past"


def create_store(path: Path) -> Store:
    """Create a persistent Oxigraph store at the given directory."""
    path.mkdir(parents=True, exist_ok=True)
    return Store(str(path))


def load_rdf(store: Store, file_path: Path, rdf_format: RdfFormat = RdfFormat.TURTLE) -> int:
    """Bulk-load an RDF file into the store. Returns the triple count after loading."""
    store.bulk_load(path=str(file_path), format=rdf_format)
    return len(store)


def execute_query(
    store: Store,
    sparql: str,
    prefix_map: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Execute a SPARQL SELECT query and return results as a list of dicts.

    If prefix_map is provided, URIs in results are compressed to prefixed form
    (e.g., http://nomisma.org/id/denarius → nm:denarius).
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
        row = {}
        for var_name in variables:
            value = solution[var_name]
            if value is None:
                row[var_name] = None
            else:
                val_str = value.value
                if compress and val_str.startswith("http"):
                    for ns, prefix in compress:
                        if val_str.startswith(ns):
                            val_str = f"{prefix}:{val_str[len(ns):]}"
                            break
                row[var_name] = val_str
        rows.append(row)
    return rows


def is_initialized(store_path: Path) -> bool:
    """Check whether a store exists and contains data."""
    if not store_path.exists():
        return False
    try:
        store = Store.read_only(str(store_path))
        return len(store) > 0
    except OSError:
        return False


def get_read_only_store(path: Path) -> Store:
    """Open an existing Oxigraph store in read-only mode."""
    return Store.read_only(str(path))
