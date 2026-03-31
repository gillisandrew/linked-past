# Blob-Level Local Readthrough Caching

## Goal

Extend `ArtifactCache` to cache individual OCI layer blobs by digest, so that dataset updates only re-download changed files. Add smart store invalidation that distinguishes data files from sidecars, avoiding full Oxigraph store rebuilds when only metadata files change.

## Motivation

Currently, any manifest digest change triggers a full re-download of all layers and a complete Oxigraph store rebuild. For large datasets (EDH: 1.6M triples, Pleiades: 3M triples), this takes minutes even when only a sidecar file (`_schema.yaml`, `_void.ttl`) changed. With per-layer caching, a schema-only update becomes instant — no data re-download, no store rebuild.

## Architecture

### Per-Layer Blob Cache

Extend `ArtifactCache` to parse OCI manifests and track individual layer digests.

**On pull:**
1. Fetch manifest JSON via `oras manifest fetch` (cheap HTTP HEAD + GET)
2. Parse the `layers` array to get per-layer digests and filenames
3. For each layer: check if `layers/{layer_digest}/` exists locally
4. Only download layers whose digests are missing
5. Assemble the blob directory by symlinking from per-layer cache

**Storage structure:**
```
{cache_dir}/
├── manifests/
│   └── ghcr.io/.../dprr/
│       ├── latest                          # text file: manifest digest
│       └── latest.json                     # NEW: full manifest JSON
├── layers/
│   ├── {sha256_digest_a}/dprr.ttl          # per-layer content store
│   ├── {sha256_digest_b}/_void.ttl
│   └── {sha256_digest_c}/_schema.yaml
├── blobs/
│   └── {manifest_digest}/                  # assembled view (symlinks)
│       ├── dprr.ttl → ../../layers/{digest_a}/dprr.ttl
│       ├── _void.ttl → ../../layers/{digest_b}/_void.ttl
│       └── _schema.yaml → ../../layers/{digest_c}/_schema.yaml
└── gc.json
```

### Manifest Parsing

**New method: `_fetch_manifest(ref) -> dict`**
- Calls `oras manifest fetch {ref}`, parses JSON
- Caches the manifest JSON alongside the digest at `manifests/{ref_path}.json`
- Returns the parsed manifest dict

**New method: `_parse_layers(manifest) -> list[LayerInfo]`**
- Extracts from each layer entry: digest, filename (from `org.opencontainers.image.title` annotation), size, is_sidecar
- `is_sidecar = filename.startswith("_")`

**New dataclass: `LayerInfo`**
```python
@dataclass
class LayerInfo:
    digest: str       # "sha256:abc123..."
    filename: str     # "dprr.ttl" or "_schema.yaml"
    size: int         # bytes
    is_sidecar: bool  # True if filename starts with "_"
```

### Modified Pull Flow

**`ArtifactCache.pull(ref, force)` changes:**

1. If not force: check existing cache (unchanged)
2. Fetch manifest via `_fetch_manifest(ref)` → get manifest dict + manifest digest
3. Parse layers via `_parse_layers(manifest)` → list of LayerInfo
4. For each layer:
   - Check if `layers/{layer_digest}/` exists and contains the file
   - If yes: cache hit (skip download)
   - If no: download this single layer (via `oras blob fetch {ref} {layer_digest}`)
5. Assemble blob directory at `blobs/{manifest_digest}/` with symlinks to layer dirs
6. Update tag→digest mapping
7. Return blob directory path

**Fallback:** If manifest fetch fails (offline, registry down), fall back to current behavior — check existing blob directory by manifest digest, or fail.

### Smart Store Invalidation

**`pull_for_dataset()` changes in `pull.py`:**

Replace the current "any digest change → nuke store" logic with file-role comparison.

```python
old_manifest = cache.get_manifest(ref)  # cached JSON from before pull
new_manifest = cache.get_manifest(ref)  # cached JSON from after pull

old_layers = {l.filename: l.digest for l in cache._parse_layers(old_manifest)}
new_layers = {l.filename: l.digest for l in cache._parse_layers(new_manifest)}

data_changed = any(
    old_layers.get(f) != new_layers.get(f)
    for f in set(old_layers) | set(new_layers)
    if not f.startswith("_")
)

if data_changed:
    shutil.rmtree(store_path)  # full rebuild needed
else:
    # Only sidecars changed — copy new sidecars, keep store
    for layer in cache._parse_layers(new_manifest):
        if layer.is_sidecar:
            src = cache._layers_dir / layer.digest.replace("sha256:", "") / layer.filename
            dst = output_dir / layer.filename
            shutil.copy2(src, dst)
```

### Layer GC

Extend `gc()` to clean up orphaned layers.

**Reference tracking:** When assembling a blob directory, record which layer digests it references. Store in `gc.json` alongside existing access times:

```json
{
  "manifests": {
    "sha256:manifest_abc": {
      "last_access": "2026-03-31T12:00:00Z",
      "layers": ["sha256:layer_1", "sha256:layer_2", "sha256:layer_3"]
    }
  }
}
```

**GC sweep (extended):**
1. Remove manifest blobs not accessed in `max_age_days` (existing behavior)
2. Collect all layer digests referenced by surviving manifests
3. Remove any layer directory not in the referenced set AND not accessed in `max_age_days`

**`cache clear` CLI:** Also wipe the `layers/` directory (in addition to existing `blobs/` and `manifests/` cleanup).

### Single-Layer Download

For downloading individual layers when only some are missing:

**Option:** Use `oras blob fetch {ref}@{layer_digest} --output {path}` to download a single blob by digest. This is a standard OCI distribution API call.

**Fallback:** If `oras blob fetch` is not available or fails, fall back to `oras pull` (downloads all layers) and populate the layer cache from the result.

## Files Changed

| File | Change |
|------|--------|
| `packages/linked-past-store/linked_past_store/cache.py` | Add `LayerInfo`, `_fetch_manifest`, `_parse_layers`, per-layer cache logic in `pull()`, layer-aware GC, `_layers_dir` property |
| `packages/linked-past-store/linked_past_store/pull.py` | Smart invalidation in `pull_for_dataset()` — compare data file digests, sidecar-only copy |
| `packages/linked-past-store/linked_past_store/cli.py` | `cache clear` wipes `layers/` directory |
| `packages/linked-past-store/tests/test_cache.py` | New tests for layer cache hit/miss, manifest parsing, GC |
| `packages/linked-past-store/tests/test_pull.py` | New tests for smart invalidation (data change vs sidecar-only change) |

## Scope Exclusions

- Delta/incremental RDF updates (SPARQL UPDATE, add/remove files) — future
- Live hot-reload of sidecars on running MCP server — future (current `update_dataset` tool handles restart-based reload)
- Changes to `push_dataset` — current push already creates per-layer artifacts with correct annotations
- Changes to the registry or plugin system — they consume files from the output directory as before

## Backward Compatibility

- Existing cache directories without `layers/` continue to work — the first pull after upgrade populates the layer cache
- The blob directory structure (under `blobs/`) is unchanged from the consumer's perspective — callers still get a directory with files, they just happen to be symlinks now
- On platforms where symlinks aren't reliable (some Windows configs), fall back to file copies

## Dependencies

- Existing: `oras` CLI (for `manifest fetch`, `blob fetch`, `pull`)
- Existing: `json` stdlib (manifest parsing)
- No new dependencies
