# Ontology Pipeline Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `ontology.py` into the packaging pipeline (generate `_schema.yaml` sidecar) and MCP runtime (fallback merge with hand-written schemas for validation and display).

**Architecture:** Packaging scripts extract empirical schemas from data and include `_schema.yaml` in OCI artifacts. At runtime, the registry loads `_schema.yaml` into metadata. Plugins merge auto-generated classes with hand-written ones — hand-written wins where both exist, auto-generated fills gaps. `get_schema` shows auto-detected classes in a separate section.

**Tech Stack:** Python 3.13, pyoxigraph, PyYAML, linked-past-store ontology module.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `packages/linked-past-store/linked_past_store/ontology.py` | Add `META_NAMESPACES` filter to `extract_from_data` |
| `packages/linked-past/linked_past/core/registry.py` | Add `_load_schema` method |
| `packages/linked-past/linked_past/core/context.py` | Add `merge_schemas` function |
| `packages/linked-past/linked_past/datasets/base.py` | Add `set_auto_schema` + update `build_schema_dict` |
| `packages/linked-past/linked_past/datasets/*/plugin.py` | Each plugin calls `set_auto_schema` during init |
| `scripts/package_*.py` (all 7) | Add schema extraction step |

---

### Task 1: Filter Metaclasses from Empirical Extraction

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/ontology.py`
- Modify: `packages/linked-past-store/tests/test_ontology.py`

- [ ] **Step 1: Add metaclass filter test**

Add to `packages/linked-past-store/tests/test_ontology.py`:

```python
SAMPLE_DATA_WITH_META = textwrap.dedent("""\
    @prefix ex: <http://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    ex:person1 a ex:Person ;
        ex:hasName "Caesar" .

    ex:Person a owl:Class ;
        rdfs:label "Person" .
""")


def test_empirical_extraction_filters_metaclasses():
    from pyoxigraph import RdfFormat
    store = Store()
    store.load(SAMPLE_DATA_WITH_META.encode(), format=RdfFormat.TURTLE)
    schema = extract_from_data(store, filter_meta=True)
    assert "Person" in schema.classes
    assert "Class" not in schema.classes
    # owl:Class should be filtered out
    for name, cls in schema.classes.items():
        assert not cls.uri.startswith("http://www.w3.org/"), f"Meta class {name} should be filtered"
```

- [ ] **Step 2: Add `filter_meta` parameter to `extract_from_data`**

In `packages/linked-past-store/linked_past_store/ontology.py`, add a constant and update `extract_from_data`:

```python
# Namespaces to filter from empirical extraction (ontology machinery, not domain classes)
_META_NAMESPACES = frozenset({
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2002/07/owl#",
})
```

Update the `extract_from_data` signature to `def extract_from_data(store: Store, *, filter_meta: bool = False) -> Schema:` and add after class collection:

```python
    if filter_meta:
        class_uris = [u for u in class_uris if not any(u.startswith(ns) for ns in _META_NAMESPACES)]
```

- [ ] **Step 3: Lint and commit**

Run: `uv run ruff check packages/linked-past-store/linked_past_store/ontology.py packages/linked-past-store/tests/test_ontology.py`

```bash
git add packages/linked-past-store/linked_past_store/ontology.py packages/linked-past-store/tests/test_ontology.py
git commit -m "feat: filter OWL/RDFS metaclasses from empirical schema extraction"
```

---

### Task 2: Add Schema Extraction to Packaging Scripts

**Files:**
- Modify: `scripts/package_dprr.py`
- Modify: `scripts/package_pleiades.py`
- Modify: `scripts/package_edh.py`
- Modify: `scripts/package_nomisma.py`
- Modify: `scripts/package_crro.py`
- Modify: `scripts/package_ocre.py`
- Modify: `scripts/package_periodo.py`

- [ ] **Step 1: Update all 7 packaging scripts**

Each script needs a new step after VoID generation. Add this import at the top of each script:

```python
from linked_past_store.ontology import extract_schema, generate_schemas_yaml
```

Then add after the `generate_void(...)` block and before the `# Push` comment:

```python
        # Extract schema
        schema = extract_schema(data_path=<data_file_var>)
        generate_schemas_yaml(schema, tmpdir / "_schema.yaml")
        print(f"Extracted schema: {len(schema.classes)} classes")
```

Where `<data_file_var>` is the verified TTL path variable for each script:
- `package_dprr.py`: `data_file`
- `package_pleiades.py`: `output`
- `package_edh.py`: `out_path`
- `package_nomisma.py`: `clean_path`
- `package_crro.py`: `ttl_path`
- `package_ocre.py`: `ttl_path`
- `package_periodo.py`: `ttl_path`

Also update each `push_dataset(...)` call to include `_schema.yaml`. Since `push_dataset` already pushes all files via `void_path`, we need to pass `_schema.yaml` as an additional file. The simplest approach: use the list form of `path`:

Replace each push call from:
```python
        digest = push_dataset(
            ref,
            <data_file>,
            annotations=annotations,
            void_path=tmpdir / "_void.ttl",
        )
```

To:
```python
        digest = push_dataset(
            ref,
            [<data_file>, tmpdir / "_void.ttl", tmpdir / "_schema.yaml"],
            annotations=annotations,
        )
```

This passes all three files as a list instead of using the separate `void_path` parameter.

- [ ] **Step 2: Lint**

Run: `uv run ruff check scripts/package_*.py`

- [ ] **Step 3: Commit**

```bash
git add scripts/package_*.py
git commit -m "feat: extract schema during packaging, include _schema.yaml in OCI artifacts"
```

---

### Task 3: Registry Loads `_schema.yaml`

**Files:**
- Modify: `packages/linked-past/linked_past/core/registry.py`

- [ ] **Step 1: Add `_load_schema` method**

Add after `_load_void` in `packages/linked-past/linked_past/core/registry.py`:

```python
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
                logger.info("Loaded auto-generated schema for %s: %d classes", name, len(classes))
        except Exception as e:
            logger.debug("Could not load schema for %s: %s", name, e)
```

- [ ] **Step 2: Call `_load_schema` from both init paths**

In `initialize_dataset`, after the `self._load_void(name, dataset_dir)` call (line that ends the `is_initialized` early-return block), add:

```python
            self._load_schema(name, dataset_dir)
```

And after the `self._load_void(name, dataset_dir)` call in the fresh-init path (after `_save_registry`):

```python
        self._load_schema(name, dataset_dir)
```

- [ ] **Step 3: Lint and commit**

Run: `uv run ruff check packages/linked-past/linked_past/core/registry.py`

```bash
git add packages/linked-past/linked_past/core/registry.py
git commit -m "feat: registry loads _schema.yaml into metadata on dataset init"
```

---

### Task 4: Schema Merge in Plugin Base Class

**Files:**
- Modify: `packages/linked-past/linked_past/core/context.py`
- Modify: `packages/linked-past/linked_past/datasets/base.py`

- [ ] **Step 1: Add `merge_schemas` to context.py**

Add to `packages/linked-past/linked_past/core/context.py`:

```python
def merge_schemas(hand_written: dict, auto_generated: dict) -> dict:
    """Merge auto-generated schema classes into hand-written schemas.

    Hand-written classes always win. Auto-generated classes are added only
    if their name doesn't exist in the hand-written schema.

    Args:
        hand_written: dict of class_name -> class_data from schemas.yaml
        auto_generated: dict of class_name -> class_data from _schema.yaml

    Returns:
        Merged dict with hand-written classes first, then new auto-generated classes.
    """
    merged = dict(hand_written)
    for cls_name, cls_data in auto_generated.items():
        if cls_name not in merged:
            merged[cls_name] = cls_data
    return merged
```

- [ ] **Step 2: Add `set_auto_schema` to DatasetPlugin base class**

In `packages/linked-past/linked_past/datasets/base.py`, add after `check_for_updates`:

```python
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
```

- [ ] **Step 3: Lint and commit**

Run: `uv run ruff check packages/linked-past/linked_past/core/context.py packages/linked-past/linked_past/datasets/base.py`

```bash
git add packages/linked-past/linked_past/core/context.py packages/linked-past/linked_past/datasets/base.py
git commit -m "feat: schema merge — hand-written wins, auto-generated fills gaps"
```

---

### Task 5: Registry Calls `set_auto_schema` on Plugins

**Files:**
- Modify: `packages/linked-past/linked_past/core/registry.py`

- [ ] **Step 1: Wire `set_auto_schema` into initialization**

In `registry.py`, update both `_load_schema` paths. After storing `meta["auto_schema"]`, call `set_auto_schema` on the plugin. Replace the end of `_load_schema`:

```python
            if classes:
                meta = self._metadata.setdefault(name, {})
                meta["auto_schema"] = classes
                # Merge into plugin's live schema
                plugin = self._plugins.get(name)
                if plugin:
                    plugin.set_auto_schema(classes)
                logger.info("Loaded auto-generated schema for %s: %d classes", name, len(classes))
```

- [ ] **Step 2: Lint and commit**

Run: `uv run ruff check packages/linked-past/linked_past/core/registry.py`

```bash
git add packages/linked-past/linked_past/core/registry.py
git commit -m "feat: registry merges auto-generated schema into plugins on init"
```

---

### Task 6: Update `get_schema` to Show Auto-Detected Classes

**Files:**
- Modify: `packages/linked-past/linked_past/core/context.py`

- [ ] **Step 1: Add `render_auto_detected_summary` function**

Add to `packages/linked-past/linked_past/core/context.py`:

```python
def render_auto_detected_summary(all_schemas: dict, hand_written_names: set[str]) -> str:
    """Render a summary of auto-detected classes not in the hand-written schema."""
    auto_only = {
        name: data for name, data in all_schemas.items()
        if name not in hand_written_names
    }
    if not auto_only:
        return ""
    lines = []
    for cls_name, cls_data in auto_only.items():
        uri = cls_data.get("uri", "")
        comment = cls_data.get("comment", "")
        if comment:
            lines.append(f"- **{cls_name}** (`{uri}`) — {comment}")
        else:
            lines.append(f"- **{cls_name}** (`{uri}`)")
    return "## Additional Classes (auto-detected)\n\n" + "\n".join(lines)
```

- [ ] **Step 2: Update each plugin's `get_schema` to append auto-detected section**

All 7 plugins have identical `get_schema` patterns. For each plugin, store the hand-written class names before merge and append the auto-detected section. The simplest approach: add `_hand_written_class_names` in `__init__` before `set_auto_schema` can be called.

In each plugin's `__init__`, after `self._schemas = load_schemas(_CONTEXT_DIR)`, add:

```python
        self._hand_written_class_names = set(self._schemas.keys())
```

Then update each plugin's `get_schema` to append the auto-detected section. After the existing return statement body, change from:

```python
        return (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )
```

To:

```python
        from linked_past.core.context import render_auto_detected_summary

        auto_section = render_auto_detected_summary(self._schemas, self._hand_written_class_names)
        result = (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )
        if auto_section:
            result += f"\n\n{auto_section}"
        return result
```

Apply this to all 7 plugins: `dprr`, `pleiades`, `edh`, `nomisma`, `crro`, `ocre`, `periodo`.

- [ ] **Step 3: Lint and commit**

Run: `uv run ruff check packages/linked-past/linked_past/core/context.py packages/linked-past/linked_past/datasets/*/plugin.py`

```bash
git add packages/linked-past/linked_past/core/context.py packages/linked-past/linked_past/datasets/
git commit -m "feat: get_schema shows auto-detected classes in separate section"
```

---

### Task 7: Push All Datasets with `_schema.yaml` and Test End-to-End

**Files:** None (runtime test)

- [ ] **Step 1: Run all 7 packaging scripts**

```bash
for ds in dprr crro periodo; do
  echo "=== $ds ==="
  uv run python scripts/package_$ds.py 2026-03-30 2>&1
done
```

```bash
for ds in ocre nomisma pleiades edh; do
  echo "=== $ds ==="
  uv run python scripts/package_$ds.py 2026-03-30 2>&1
done
```

Expected: each script prints `Extracted schema: N classes` before pushing.

- [ ] **Step 2: Pull `_schema.yaml` into local dataset dirs**

```bash
for ds in dprr pleiades edh nomisma crro ocre periodo; do
  oras pull "ghcr.io/gillisandrew/linked-past/$ds:2026-03-30" \
    -o "$HOME/.local/share/linked-past/$ds/" -k 2>&1 | grep -E "schema|Error"
done
```

- [ ] **Step 3: Test MCP integration**

```python
uv run python -c "
from pathlib import Path
from linked_past.core.registry import DatasetRegistry
from linked_past.datasets.dprr.plugin import DPRRPlugin

data_dir = Path.home() / '.local/share/linked-past'
registry = DatasetRegistry(data_dir=data_dir)
registry.register(DPRRPlugin())
registry.initialize_cached()

plugin = registry.get_plugin('dprr')
schema_dict = plugin.build_schema_dict()
print(f'Schema dict classes: {len(schema_dict)}')
print(f'Hand-written: {len(plugin._hand_written_class_names)}')
print(f'New from auto: {len(schema_dict) - len(plugin._hand_written_class_names)}')
"
```

Expected: more classes in schema_dict than hand-written alone.

- [ ] **Step 4: Final lint**

Run: `uv run ruff check packages/linked-past/ packages/linked-past-store/ scripts/`
