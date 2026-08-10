"""SQLite indexes must be usable from worker threads.

The stateless Streamable HTTP transport (MCP 2026-07-28) dispatches sync tool
calls on anyio worker threads, while the shared AppContext — and its SQLite
connections — is built on the startup thread. Connections therefore need
check_same_thread=False (safe: sqlite3.threadsafety == 3 serializes access).
"""

from concurrent.futures import ThreadPoolExecutor

from linked_past.core.meta_entities import MetaEntityIndex
from linked_past.core.search import SearchIndex
from linked_past.core.vector import VectorIndex


def _in_thread(fn):
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fn).result()


def test_search_index_cross_thread():
    index = SearchIndex()
    index.add("dprr", "example", "consuls of the republic")
    assert _in_thread(lambda: index.search("consuls")) != []


def test_vector_index_cross_thread(tmp_path):
    index = VectorIndex(tmp_path / "vec.db")
    from linked_past.core.vector import VECTOR_DIM

    assert _in_thread(lambda: index.search([0.0] * VECTOR_DIM, k=1)) == []


def test_meta_entity_index_cross_thread(tmp_path):
    index = MetaEntityIndex(tmp_path / "meta.db")
    assert _in_thread(lambda: index.search("anything")) == []
