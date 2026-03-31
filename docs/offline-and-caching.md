# Offline Operation and Caching

How linked-past behaves when the OCI registry is unreachable and how the multi-layer caching system works.

## Offline Behavior

linked-past is designed to work fully offline once datasets have been pulled. The server only contacts the OCI registry when explicitly asked to via `update_dataset`.

### Startup (Always Offline)

Server startup never contacts the network. `initialize_cached()` only opens Oxigraph stores already present on disk. If no datasets have been pulled yet, the server starts with zero datasets loaded — all tools still respond, but queries return "dataset not initialized" errors until `update_dataset` is called.

### Query Execution (Always Offline)

All SPARQL queries, entity searches, link discovery, and provenance lookups run against local Oxigraph stores. No upstream SPARQL endpoints are contacted.

### Dataset Updates (Requires Network)

`update_dataset` is the only operation that contacts the OCI registry. If the registry is unreachable:

- **Dataset already cached locally**: The tool reports the current local status (version, triple count). No error is raised.
- **Dataset not yet pulled**: The tool reports an error explaining that the dataset could not be downloaded. The error includes the OCI reference that was attempted.
- **Force update requested**: The tool deletes the local store first, then attempts to pull. If the pull fails, the dataset becomes unloaded until the next successful pull. This is the one destructive failure mode — avoid `force=True` when offline.

### Embedding Index (Always Offline)

The fastembed model is downloaded once on first startup and cached locally by the fastembed library (in its own cache directory, typically `~/.cache/fastembed/`). Subsequent startups use the cached model. If the model has never been downloaded and the network is unavailable, embedding-based features (`discover_datasets` with a topic, semantic search) will fail, but all other tools work normally.

## Caching Architecture

There are three independent caching layers:

```
┌─────────────────────────────────────────┐
│  Layer 1: OCI Artifact Cache            │
│  (linked-past-store, content-addressed) │
│  ~/.cache/linked-past/                  │
└─────────────────┬───────────────────────┘
                  │ pull_dataset() copies files
                  ▼
┌─────────────────────────────────────────┐
│  Layer 2: Dataset Data Directory        │
│  (raw RDF + Oxigraph stores)            │
│  ~/.local/share/linked-past/            │
└─────────────────┬───────────────────────┘
                  │ server reads stores
                  ▼
┌─────────────────────────────────────────┐
│  Layer 3: Server Runtime Indexes        │
│  (embeddings, meta-entities, linkage)   │
│  In-memory + SQLite                     │
└─────────────────────────────────────────┘
```

### Layer 1: OCI Artifact Cache

**Location**: `LINKED_PAST_CACHE_DIR` > `$XDG_CACHE_HOME/linked-past` > `~/.cache/linked-past/`

**Layout**:
```
{cache_dir}/
├── manifests/           # tag → digest mappings
│   └── ghcr.io/
│       └── gillisandrew/linked-past/
│           └── datasets/dprr/
│               ├── latest         # contains: sha256:2aee...
│               └── latest.json    # full manifest JSON
├── layers/              # per-layer content-addressable storage
│   └── sha256/
│       └── {digest}/
│           └── dprr.ttl
├── blobs/               # assembled artifacts (symlinks to layers)
│   └── sha256/
│       └── {manifest_digest}/
│           ├── dprr.ttl → ../../layers/sha256/{layer_digest}/dprr.ttl
│           ├── _void.ttl → ...
│           └── _schema.yaml → ...
└── gc.json              # last-access timestamps for garbage collection
```

**How it works**:

1. **Tag resolution**: `oras manifest fetch --descriptor` resolves a tag (e.g., `latest`) to a manifest digest without downloading data.

2. **Cache hit by tag**: If the tag file exists and the digest matches, the blob directory is returned immediately (no network call beyond tag resolution).

3. **Cache hit by digest**: If the tag changed but the manifest digest matches an existing blob directory, the tag mapping is updated and the cached data is reused.

4. **Layer-aware pull**: The manifest is fetched and parsed into layers. Only layers not already in the `layers/` directory are downloaded. Each downloaded layer is verified against its SHA-256 digest. The blob directory is then assembled from symlinks to cached layers.

5. **Fallback**: If manifest fetching fails (e.g., older registry), falls back to a full `oras pull` of the entire artifact.

**Change detection**:

When `pull_for_dataset()` detects a digest change, it classifies the change:
- **Data files changed**: The local Oxigraph store is deleted (invalidated) so it gets rebuilt on next initialization.
- **Only sidecar files changed** (VoID, schema): The sidecars are updated in place. The store is **not** invalidated, since the actual RDF data hasn't changed.
- **No change**: Nothing happens.

**Garbage collection**:

`ArtifactCache.gc(max_age_days=30)` removes blobs and orphaned layers not accessed within the specified period. Layer GC is reference-counted — a layer is only removed if no surviving manifest references it AND it hasn't been accessed recently.

### Layer 2: Dataset Data Directory

**Location**: `LINKED_PAST_DATA_DIR` > `$XDG_DATA_HOME/linked-past` > `~/.local/share/linked-past/`

This is where the server reads data from. Each dataset gets its own subdirectory containing:

- Raw RDF files (copied from the OCI cache)
- An Oxigraph persistent store (built by loading the RDF into Oxigraph)
- Sidecar metadata (`_void.ttl`, `_schema.yaml`)

**`registry.json`** at the root tracks version, triple count, license, and fetch timestamp for each initialized dataset. This is read on startup to populate dataset metadata without re-counting triples.

**Store lifecycle**:
1. First pull: RDF copied from OCI cache → loaded into new Oxigraph store → store closed → reopened read-only.
2. Subsequent startups: Store opened read-only directly. No RDF parsing.
3. Update with changed data: Store directory deleted → rebuilt from new RDF on next init.
4. Force update: Store directory deleted before pull → rebuilt after fresh download.

### Layer 3: Server Runtime Indexes

Built at startup from the data directory contents:

- **Embedding index** (`embeddings.db`): SQLite database of fastembed vectors for semantic search. Rebuilt when datasets change. Persists across restarts.
- **Meta-entity index** (`meta_entities.db`): SQLite cache of clustered cross-dataset entities. Rebuilt from the linkage graph when it changes.
- **Linkage graph**: In-memory Oxigraph store, rebuilt from YAML + Turtle files on every startup (not cached to disk).

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LINKED_PAST_DATA_DIR` | `~/.local/share/linked-past/` | Dataset stores and metadata |
| `LINKED_PAST_CACHE_DIR` | `~/.cache/linked-past/` | OCI artifact cache |
| `LINKED_PAST_REGISTRY` | `ghcr.io/gillisandrew/linked-past` | OCI registry for dataset pulls |
| `LINKED_PAST_QUERY_TIMEOUT` | `600` | SPARQL query timeout in seconds |

## Clearing Caches

To reset everything and re-download all data:

```bash
# Remove OCI artifact cache (forces re-download)
rm -rf ~/.cache/linked-past/

# Remove dataset stores (forces re-initialization)
rm -rf ~/.local/share/linked-past/

# Restart the server and use update_dataset to re-pull
```

To clear only one dataset:

```bash
# Remove just the dataset's store (will rebuild from cached OCI artifact)
rm -rf ~/.local/share/linked-past/dprr/store/

# Or remove the dataset entirely (will re-download from OCI)
rm -rf ~/.local/share/linked-past/dprr/
```
