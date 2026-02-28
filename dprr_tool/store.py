import os
from pathlib import Path

from pyoxigraph import RdfFormat, Store


def get_data_dir() -> Path:
    """Compute the DPRR data directory.

    Precedence: DPRR_DATA_DIR > $XDG_DATA_HOME/dprr-tool > ~/.local/share/dprr-tool
    """
    explicit = os.environ.get("DPRR_DATA_DIR")
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "dprr-tool"


def get_or_create_store(path: Path) -> Store:
    """Open or create a persistent Oxigraph store at the given directory."""
    path.mkdir(parents=True, exist_ok=True)
    return Store(str(path))


def load_rdf(store: Store, file_path: Path) -> int:
    """Bulk-load a Turtle RDF file into the store. Returns the number of triples after loading."""
    store.bulk_load(
        path=str(file_path),
        format=RdfFormat.TURTLE,
    )
    return len(store)


def execute_query(store: Store, sparql: str) -> list[dict[str, str]]:
    """Execute a SPARQL SELECT query and return results as a list of dicts.

    Only SELECT queries are supported. CONSTRUCT, ASK, and DESCRIBE queries
    raise a ValueError with a descriptive message.
    """
    results = store.query(sparql)
    if not hasattr(results, "variables"):
        raise ValueError(
            "Only SELECT queries are supported. "
            "CONSTRUCT, ASK, and DESCRIBE queries are not implemented."
        )
    variables = [v.value for v in results.variables]
    rows = []
    for solution in results:
        row = {}
        for var_name in variables:
            value = solution[var_name]
            if value is not None:
                row[var_name] = value.value
            else:
                row[var_name] = None
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
    """Open an existing Oxigraph store in read-only mode (no file locking)."""
    return Store.read_only(str(path))


def ensure_initialized(store_path: Path, rdf_file: str | None = None) -> Store:
    """Open the store, auto-loading RDF data from rdf_file if the store is empty.

    Returns a read-only store when data already exists to avoid file locking.
    If rdf_file is None, reads from the DPRR_RDF_FILE environment variable.
    Raises RuntimeError if the store is empty and no RDF file is available.
    """
    if is_initialized(store_path):
        return get_read_only_store(store_path)

    rdf_path = rdf_file or os.environ.get("DPRR_RDF_FILE")
    if not rdf_path:
        raise RuntimeError(
            "Store is empty and no RDF file provided. "
            "Set DPRR_RDF_FILE environment variable."
        )

    path = Path(rdf_path)
    if not path.exists():
        raise RuntimeError(f"RDF file not found: {path}")

    store = get_or_create_store(store_path)
    load_rdf(store, path)
    del store
    return get_read_only_store(store_path)
