# Data Pipeline Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the monolithic `package_*.py` scripts into a three-stage pipeline (ingest → clean → validate) with a central `datasets.yaml` config as single source of truth.

**Architecture:** Ingest scripts push raw Turtle to `raw/` OCI namespace. A generic clean script pulls raw artifacts, sanitizes, generates metadata, and pushes to `datasets/`. A generic validate script checks triple counts and schema diffs. CI workflow orchestrates clean + validate.

**Tech Stack:** Python 3.13, linked-past-store (push/pull/sanitize/verify/void/ontology), PyYAML, oras CLI, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-03-31-data-pipeline-design.md`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `datasets.yaml` | Central config: OCI refs, annotations, thresholds, citations |
| Create | `scripts/pipeline_config.py` | Load + parse `datasets.yaml`, render BibTeX to plain text |
| Create | `scripts/ingest_dprr.py` | Fetch DPRR tar.gz → push raw |
| Create | `scripts/ingest_pleiades.py` | Fetch Pleiades tar.gz → push raw |
| Create | `scripts/ingest_periodo.py` | Fetch PeriodO JSON-LD → convert → push raw |
| Create | `scripts/ingest_nomisma.py` | Fetch Nomisma RDF/XML → convert → push raw |
| Create | `scripts/ingest_edh.py` | Read local zip → push raw |
| Create | `scripts/ingest_generic.py` | Generic fetch + convert from `fetch_url`/`source_format` |
| Create | `scripts/clean_dataset.py` | Pull raw → sanitize → verify → VoID → schema → push clean |
| Create | `scripts/validate_dataset.py` | Pull clean → triple count check → schema diff |
| Create | `.github/workflows/clean-datasets.yml` | CI: clean + validate workflow |
| Delete | `scripts/package_dprr.py` | Replaced by ingest + clean |
| Delete | `scripts/package_pleiades.py` | Replaced by ingest + clean |
| Delete | `scripts/package_periodo.py` | Replaced by ingest + clean |
| Delete | `scripts/package_nomisma.py` | Replaced by ingest + clean |
| Delete | `scripts/package_crro.py` | Replaced by ingest + clean |
| Delete | `scripts/package_ocre.py` | Replaced by ingest + clean |
| Delete | `scripts/package_edh.py` | Replaced by ingest + clean |
| Delete | `.github/workflows/update-datasets.yml` | Replaced by clean-datasets.yml |

---

### Task 1: Create `datasets.yaml`

**Files:**
- Create: `datasets.yaml`

- [ ] **Step 1: Write `datasets.yaml`**

```yaml
dprr:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/dprr:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/dprr:latest
  ingest_script: scripts/ingest_dprr.py
  min_triple_count: 600000
  license: CC-BY-NC-4.0
  source_url: https://romanrepublic.ac.uk
  description: "Digital Prosopography of the Roman Republic — persons, offices, relationships (509-31 BC)"
  citation: |
    @misc{mouritsen2017dprr,
      author       = {Mouritsen, Henrik and Rathbone, Dominic and Bradley, John and Robb, Maggie},
      title        = {{Digital Prosopography of the Roman Republic}},
      year         = {2017},
      howpublished = {\url{https://romanrepublic.ac.uk/}},
      publisher    = {King's College London},
      note         = {AHRC-funded project. Maintained by King's Digital Lab. CC BY-NC 4.0}
    }

pleiades:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/pleiades:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/pleiades:latest
  ingest_script: scripts/ingest_pleiades.py
  min_triple_count: 2500000
  license: CC-BY-3.0
  source_url: https://pleiades.stoa.org/
  description: "Gazetteer of ancient places — coordinates, names, time periods"
  citation: |
    @misc{pleiades,
      author       = {Bagnall, Roger and Talbert, Richard and Elliott, Tom and Gillies, Sean},
      title        = {Pleiades: A Gazetteer of Past Places},
      howpublished = {\url{https://pleiades.stoa.org/}},
      year         = {2006--2025},
      doi          = {10.5281/zenodo.1193921},
      note         = {CC BY 3.0}
    }

periodo:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/periodo:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/periodo:latest
  ingest_script: scripts/ingest_periodo.py
  min_triple_count: 170000
  license: CC0-1.0
  source_url: https://perio.do/
  description: "Gazetteer of period definitions from scholarly sources"
  citation: |
    @misc{periodo,
      author       = {Rabinowitz, Adam and Shaw, Ryan},
      title        = {{PeriodO}: A Gazetteer of Period Definitions},
      howpublished = {\url{https://perio.do/}},
      year         = {2014--2026},
      note         = {Canonical dataset: \url{http://n2t.net/ark:/99152/p0d}. CC0 1.0}
    }

nomisma:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/nomisma:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/nomisma:latest
  ingest_script: scripts/ingest_nomisma.py
  min_triple_count: 400000
  license: CC-BY-4.0
  source_url: http://nomisma.org/
  description: "Numismatic concept vocabulary — persons, mints, denominations"
  citation: |
    @misc{nomisma_org,
      author       = {Gruber, Ethan and Meadows, Andrew and Heath, Sebastian},
      title        = {{Nomisma.org: Linked Open Data for Numismatics}},
      howpublished = {\url{http://nomisma.org/}},
      year         = {2010},
      note         = {American Numismatic Society, ISAW (NYU), DAI. CC BY 4.0}
    }

crro:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/crro:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/crro:latest
  ingest_script: scripts/ingest_generic.py
  fetch_url: https://numismatics.org/crro/nomisma.rdf
  source_format: rdf-xml
  min_triple_count: 50000
  license: ODbL-1.0
  source_url: https://numismatics.org/crro/
  description: "Roman Republican coin types (Crawford's RRC) — 2,602 types with iconography and Nomisma links"
  citation: |
    @misc{gruber_crro,
      author       = {Gruber, Ethan},
      title        = {{Coinage of the Roman Republic Online (CRRO)}},
      year         = {2015},
      howpublished = {\url{https://numismatics.org/crro/}},
      note         = {American Numismatic Society. Based on Crawford, M.H. (1974) Roman Republican Coinage. ODbL 1.0}
    }

ocre:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/ocre:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/ocre:latest
  ingest_script: scripts/ingest_generic.py
  fetch_url: https://numismatics.org/ocre/nomisma.rdf
  source_format: rdf-xml
  min_triple_count: 1100000
  license: ODbL-1.0
  source_url: https://numismatics.org/ocre/
  description: "Roman Imperial coin types (RIC) — ~50,000 types with iconography and Nomisma links"
  citation: |
    @misc{gruber_ocre,
      author       = {Gruber, Ethan},
      title        = {{Online Coins of the Roman Empire (OCRE)}},
      year         = {2012},
      howpublished = {\url{https://numismatics.org/ocre/}},
      note         = {American Numismatic Society and ISAW (NYU). ODbL 1.0}
    }

edh:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/edh:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/edh:latest
  ingest_script: scripts/ingest_edh.py
  min_triple_count: 1500000
  license: CC-BY-SA-4.0
  source_url: https://edh.ub.uni-heidelberg.de/
  description: "81,000+ Latin inscriptions with transcriptions, findspots, and dates"
  citation: |
    @misc{edh,
      author       = {{Epigraphic Database Heidelberg}},
      title        = {Epigraphic Database Heidelberg},
      howpublished = {\url{https://edh.ub.uni-heidelberg.de/}},
      year         = {1997--2021},
      note         = {Founded by G\'eza Alf\"oldy; directed by Christian Witschel. Heidelberg Academy of Sciences and Humanities. CC BY-SA 4.0}
    }
```

- [ ] **Step 2: Commit**

```bash
git add datasets.yaml
git commit -m "feat: add datasets.yaml as single source of truth for pipeline config"
```

---

### Task 2: Create `scripts/pipeline_config.py`

Shared config loader used by all pipeline scripts. Loads `datasets.yaml`, builds OCI annotation dicts, renders BibTeX citations to plain text.

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/tests/__init__.py`
- Create: `scripts/pipeline_config.py`
- Create: `scripts/tests/test_pipeline_config.py`
- Modify: `pyproject.toml` (add `scripts/tests` to testpaths)

- [ ] **Step 1: Create package directories and `__init__.py` files**

```bash
mkdir -p scripts/tests
touch scripts/__init__.py scripts/tests/__init__.py
```

- [ ] **Step 2: Add `scripts/tests` to testpaths in `pyproject.toml`**

In `pyproject.toml`, change:
```toml
testpaths = ["packages/linked-past/tests", "packages/linked-past-store/tests"]
```
to:
```toml
testpaths = ["packages/linked-past/tests", "packages/linked-past-store/tests", "scripts/tests"]
```

- [ ] **Step 3: Write failing tests**

```python
# scripts/tests/test_pipeline_config.py
"""Tests for pipeline_config module."""

import textwrap

import pytest
import yaml


@pytest.fixture
def sample_config(tmp_path):
    """Write a minimal datasets.yaml and return its path."""
    data = {
        "test_dataset": {
            "raw_ref": "ghcr.io/test/raw/test:latest",
            "clean_ref": "ghcr.io/test/datasets/test:latest",
            "ingest_script": "scripts/ingest_generic.py",
            "fetch_url": "https://example.org/data.rdf",
            "source_format": "rdf-xml",
            "min_triple_count": 1000,
            "license": "CC-BY-4.0",
            "source_url": "https://example.org",
            "description": "Test dataset",
            "citation": textwrap.dedent("""\
                @misc{test2024,
                  author = {Smith, John},
                  title  = {Test Dataset},
                  year   = {2024},
                  note   = {CC BY 4.0}
                }
            """),
        }
    }
    config_path = tmp_path / "datasets.yaml"
    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return config_path


def test_load_config(sample_config):
    from scripts.pipeline_config import load_config

    config = load_config(sample_config)
    assert "test_dataset" in config
    assert config["test_dataset"]["license"] == "CC-BY-4.0"
    assert config["test_dataset"]["min_triple_count"] == 1000


def test_load_dataset_config(sample_config):
    from scripts.pipeline_config import load_dataset_config

    ds = load_dataset_config("test_dataset", sample_config)
    assert ds["raw_ref"] == "ghcr.io/test/raw/test:latest"
    assert ds["clean_ref"] == "ghcr.io/test/datasets/test:latest"


def test_load_dataset_config_unknown(sample_config):
    from scripts.pipeline_config import load_dataset_config

    with pytest.raises(KeyError, match="no_such_dataset"):
        load_dataset_config("no_such_dataset", sample_config)


def test_render_citation_to_text():
    from scripts.pipeline_config import render_citation

    bibtex = textwrap.dedent("""\
        @misc{test2024,
          author = {Smith, John},
          title  = {Test Dataset},
          year   = {2024},
          note   = {CC BY 4.0}
        }
    """)
    text = render_citation(bibtex)
    assert "Smith" in text
    assert "Test Dataset" in text
    assert "2024" in text


def test_render_citation_double_braces():
    """BibTeX titles often use double braces for capitalization preservation."""
    from scripts.pipeline_config import render_citation

    bibtex = textwrap.dedent("""\
        @misc{dprr,
          author = {Mouritsen, Henrik},
          title  = {{Digital Prosopography of the Roman Republic}},
          year   = {2017}
        }
    """)
    text = render_citation(bibtex)
    assert "Digital Prosopography" in text
    assert "Mouritsen" in text


def test_render_citation_empty():
    from scripts.pipeline_config import render_citation

    assert render_citation("") == ""


def test_render_citation_url_field():
    """Should fall back to url field if howpublished is absent."""
    from scripts.pipeline_config import render_citation

    bibtex = textwrap.dedent("""\
        @misc{test,
          author = {Smith, John},
          title  = {Test},
          year   = {2024},
          url    = {https://example.org}
        }
    """)
    text = render_citation(bibtex)
    assert "https://example.org" in text


def test_build_annotations(sample_config):
    from scripts.pipeline_config import build_annotations, load_dataset_config

    ds = load_dataset_config("test_dataset", sample_config)
    annotations = build_annotations(ds, "test_dataset")
    assert annotations["org.opencontainers.image.licenses"] == "CC-BY-4.0"
    assert annotations["org.opencontainers.image.source"] == "https://example.org"
    assert annotations["io.github.gillisandrew.linked-past.dataset"] == "test_dataset"
    assert "Smith" in annotations["io.github.gillisandrew.linked-past.citation"]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest scripts/tests/test_pipeline_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.pipeline_config'`

- [ ] **Step 5: Write implementation**

```python
# scripts/pipeline_config.py
"""Load datasets.yaml config and build OCI annotations for pipeline scripts."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "datasets.yaml"


def load_config(config_path: Path | None = None) -> dict:
    """Load the full datasets.yaml config."""
    path = config_path or _CONFIG_PATH
    with open(path) as f:
        return yaml.safe_load(f)


def load_dataset_config(dataset: str, config_path: Path | None = None) -> dict:
    """Load config for a single dataset. Raises KeyError if not found."""
    config = load_config(config_path)
    if dataset not in config:
        available = ", ".join(config.keys())
        raise KeyError(f"Unknown dataset {dataset!r}. Available: {available}")
    return config[dataset]


def render_citation(bibtex: str) -> str:
    """Render a BibTeX entry to a plain-text citation string.

    Extracts author, title, year, howpublished/url, and note fields
    and formats them as: "Author (Year). Title. URL. Note."
    Handles double-brace BibTeX titles like {{My Title}}.
    """
    if not bibtex.strip():
        return ""

    def _extract(field: str) -> str:
        # Match field = {content}, handling nested braces by consuming
        # everything between the outermost braces greedily then trimming
        pattern = rf"{field}\s*=\s*\{{(.*)\}}"
        match = re.search(pattern, bibtex, re.DOTALL)
        if not match:
            return ""
        # Take only up to the first "},\n" or "}\n" to avoid grabbing next field
        value = match.group(1)
        # Trim at first unbalanced close brace (handles greedy overshoot)
        depth = 0
        for i, ch in enumerate(value):
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    value = value[:i]
                    break
                depth -= 1
        value = value.strip()
        # Clean up LaTeX commands
        value = re.sub(r"\\url\{([^}]*)\}", r"\1", value)
        # Strip remaining braces (e.g., {Title} → Title)
        value = value.replace("{", "").replace("}", "")
        value = value.replace("\\", "")
        return value.strip()

    author = _extract("author")
    title = _extract("title")
    year = _extract("year")
    url = _extract("howpublished") or _extract("url")
    note = _extract("note")

    parts = []
    if author and year:
        parts.append(f"{author} ({year})")
    elif author:
        parts.append(author)
    if title:
        parts.append(title)
    if url:
        parts.append(url)
    if note:
        parts.append(note)
    return ". ".join(parts) + ("." if parts else "")


def build_annotations(ds_config: dict, dataset_name: str) -> dict[str, str]:
    """Build OCI manifest annotations from a dataset config entry."""
    citation_text = render_citation(ds_config.get("citation", ""))
    return {
        "org.opencontainers.image.source": ds_config["source_url"],
        "org.opencontainers.image.description": ds_config["description"],
        "org.opencontainers.image.licenses": ds_config["license"],
        "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
        "io.github.gillisandrew.linked-past.dataset": dataset_name,
        "io.github.gillisandrew.linked-past.format": "text/turtle",
        "io.github.gillisandrew.linked-past.citation": citation_text,
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest scripts/tests/test_pipeline_config.py -v`
Expected: All 8 tests PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/pipeline_config.py scripts/tests/test_pipeline_config.py scripts/__init__.py scripts/tests/__init__.py pyproject.toml
git commit -m "feat: add pipeline_config module for datasets.yaml loading and annotation building"
```

---

### Task 3: Create `scripts/ingest_generic.py`

Generic ingest script for datasets that use `fetch_url` + `source_format`. Used by CRRO and OCRE.

**Files:**
- Create: `scripts/ingest_generic.py`

- [ ] **Step 1: Write the script**

```python
# scripts/ingest_generic.py
"""Generic dataset ingest: download from fetch_url, convert to Turtle, push to raw OCI."""

import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config


def main(dataset: str):
    ds = load_dataset_config(dataset)

    fetch_url = ds.get("fetch_url")
    source_format = ds.get("source_format")
    if not fetch_url or not source_format:
        print(f"ERROR: {dataset} requires fetch_url and source_format for generic ingest")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Download
        print(f"Downloading {fetch_url}...")
        raw_path = tmpdir / f"{dataset}_raw"
        urllib.request.urlretrieve(fetch_url, str(raw_path))
        print(f"Downloaded ({raw_path.stat().st_size:,} bytes)")

        # Convert to Turtle
        ttl_path = tmpdir / f"{dataset}.ttl"
        if source_format == "rdf-xml":
            print("Converting RDF/XML to Turtle via rapper...")
            with open(ttl_path, "w") as ttl_out:
                subprocess.run(
                    ["rapper", "-i", "rdfxml", "-o", "turtle", str(raw_path)],
                    stdout=ttl_out,
                    stderr=subprocess.PIPE,
                    check=True,
                )
        elif source_format == "json-ld":
            print("Converting JSON-LD to Turtle via rdflib...")
            from rdflib import Graph

            g = Graph()
            g.parse(str(raw_path), format="json-ld")
            g.serialize(str(ttl_path), format="turtle")
        elif source_format == "turtle":
            import shutil

            shutil.copy2(raw_path, ttl_path)
        else:
            print(f"ERROR: Unknown source_format {source_format!r}")
            sys.exit(1)

        print(f"Created {ttl_path.name} ({ttl_path.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, dataset),
            "io.github.gillisandrew.linked-past.source-url": fetch_url,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, ttl_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ingest_generic.py <dataset>")
        sys.exit(1)
    main(sys.argv[1])
```

- [ ] **Step 2: Commit**

```bash
git add scripts/ingest_generic.py
git commit -m "feat: add generic ingest script for fetch_url + source_format datasets"
```

---

### Task 4: Create custom ingest scripts

**Files:**
- Create: `scripts/ingest_dprr.py`
- Create: `scripts/ingest_pleiades.py`
- Create: `scripts/ingest_periodo.py`
- Create: `scripts/ingest_nomisma.py`
- Create: `scripts/ingest_edh.py`

Each script follows the same pattern: read config from `datasets.yaml`, fetch upstream data with dataset-specific logic, push raw Turtle to `raw_ref`.

- [ ] **Step 1: Write `scripts/ingest_dprr.py`**

```python
# scripts/ingest_dprr.py
"""Ingest DPRR: download tar.gz from GitHub release, push raw Turtle to OCI."""

import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"


def main():
    ds = load_dataset_config("dprr")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(FETCH_URL)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extract("dprr.ttl", path=str(tmpdir), filter="data")
        Path(tmp_path).unlink()

        data_file = tmpdir / "dprr.ttl"
        print(f"Extracted dprr.ttl ({data_file.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, "dprr"),
            "io.github.gillisandrew.linked-past.source-url": FETCH_URL,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, data_file, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `scripts/ingest_pleiades.py`**

```python
# scripts/ingest_pleiades.py
"""Ingest Pleiades: download tar.gz, concatenate Turtle files, push raw to OCI."""

import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "https://atlantides.org/downloads/pleiades/rdf/pleiades-latest.tar.gz"


def main():
    ds = load_dataset_config("pleiades")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(FETCH_URL)

        print("Extracting and concatenating Turtle files...")
        output = tmpdir / "pleiades.ttl"
        with tarfile.open(tmp_path, "r:gz") as tar, open(output, "w") as out:
            for member in sorted(tar.getnames()):
                if member.endswith(".ttl"):
                    f = tar.extractfile(member)
                    if f:
                        out.write(f"# Source: {member}\n")
                        out.write(f.read().decode("utf-8"))
                        out.write("\n\n")
        Path(tmp_path).unlink()
        print(f"Created pleiades.ttl ({output.stat().st_size:,} bytes)")

        # Push raw (unsanitized — clean step handles BCP 47 fixes)
        annotations = {
            **build_annotations(ds, "pleiades"),
            "io.github.gillisandrew.linked-past.source-url": FETCH_URL,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, output, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write `scripts/ingest_periodo.py`**

```python
# scripts/ingest_periodo.py
"""Ingest PeriodO: download JSON-LD, convert to Turtle via rdflib, push raw to OCI."""

import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "http://n2t.net/ark:/99152/p0d.jsonld"


def main():
    ds = load_dataset_config("periodo")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        jsonld_path = tmpdir / "periodo.jsonld"
        urllib.request.urlretrieve(FETCH_URL, str(jsonld_path))
        print(f"Downloaded ({jsonld_path.stat().st_size:,} bytes)")

        print("Converting JSON-LD to Turtle...")
        from rdflib import Graph

        g = Graph()
        g.parse(str(jsonld_path), format="json-ld")
        ttl_path = tmpdir / "periodo.ttl"
        g.serialize(str(ttl_path), format="turtle")
        print(f"Created periodo.ttl ({ttl_path.stat().st_size:,} bytes), {len(g)} triples")

        # Push raw
        annotations = {
            **build_annotations(ds, "periodo"),
            "io.github.gillisandrew.linked-past.source-url": FETCH_URL,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, ttl_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `scripts/ingest_nomisma.py`**

```python
# scripts/ingest_nomisma.py
"""Ingest Nomisma: download RDF/XML, convert to Turtle via rapper, push raw to OCI.

Removes lines with Unicode replacement characters (bad IRIs in upstream data).
"""

import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "https://nomisma.org/nomisma.org.rdf"
_BAD_UNICODE = re.compile(r".*\ufffd.*\n?")


def main():
    ds = load_dataset_config("nomisma")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        rdf_path = tmpdir / "nomisma.rdf"
        urllib.request.urlretrieve(FETCH_URL, str(rdf_path))
        print(f"Downloaded ({rdf_path.stat().st_size:,} bytes)")

        print("Converting RDF/XML to Turtle via rapper...")
        raw_ttl = tmpdir / "nomisma_raw.ttl"
        with open(raw_ttl, "w") as ttl_out:
            subprocess.run(
                ["rapper", "-i", "rdfxml", "-o", "turtle", "-q", str(rdf_path)],
                stdout=ttl_out,
                stderr=subprocess.PIPE,
                check=False,  # rapper returns 1 for warnings
            )

        # Remove lines with bad Unicode
        text = raw_ttl.read_text(errors="replace")
        clean_text, fix_count = _BAD_UNICODE.subn("", text)
        ttl_path = tmpdir / "nomisma.ttl"
        ttl_path.write_text(clean_text)
        if fix_count:
            print(f"Removed {fix_count} lines with bad Unicode")
        print(f"Created nomisma.ttl ({ttl_path.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, "nomisma"),
            "io.github.gillisandrew.linked-past.source-url": FETCH_URL,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, ttl_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Write `scripts/ingest_edh.py`**

```python
# scripts/ingest_edh.py
"""Ingest EDH: extract Turtle from local zip, push raw to OCI."""

import sys
import tempfile
import zipfile
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

LOCAL_ZIP = Path(__file__).parent.parent / "edh_linked_data.zip"


def main():
    ds = load_dataset_config("edh")

    if not LOCAL_ZIP.exists():
        print(f"ERROR: {LOCAL_ZIP} not found. Place edh_linked_data.zip in the project root.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Extracting {LOCAL_ZIP}...")
        with zipfile.ZipFile(LOCAL_ZIP) as zf:
            zf.extractall(tmpdir / "raw")

        ttl_files = sorted((tmpdir / "raw").glob("*.ttl"))
        print(f"Found {len(ttl_files)} Turtle files")

        out_path = tmpdir / "edh.ttl"
        with open(out_path, "w") as out:
            for i, ttl in enumerate(ttl_files):
                if i > 0:
                    out.write("\n")
                out.write(ttl.read_text())
        print(f"Created edh.ttl ({out_path.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, "edh"),
            "io.github.gillisandrew.linked-past.source-url": "https://edh.ub.uni-heidelberg.de/data/export",
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, out_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add scripts/ingest_dprr.py scripts/ingest_pleiades.py scripts/ingest_periodo.py scripts/ingest_nomisma.py scripts/ingest_edh.py
git commit -m "feat: add per-dataset ingest scripts for raw OCI artifact ingestion"
```

---

### Task 5: Create `scripts/clean_dataset.py` (depends on Task 6)

Generic clean script. Pulls raw OCI artifact, sanitizes, verifies, generates VoID + schema, runs schema diff, pushes clean artifact with provenance. Imports `diff_schemas` from `validate_dataset.py`.

**Files:**
- Create: `scripts/clean_dataset.py`

- [ ] **Step 1: Write the script**

```python
# scripts/clean_dataset.py
"""Clean a raw dataset: pull from raw OCI, sanitize, verify, generate metadata, push clean.

Also runs schema diff against the previous version (if available) before pushing,
since both schemas are in memory at that point.
"""

import sys
import tempfile
from pathlib import Path

import yaml

from linked_past_store import (
    ArtifactCache,
    pull_dataset,
    push_dataset,
    sanitize_turtle,
    verify_turtle,
)
from linked_past_store.ontology import extract_schema, generate_schemas_yaml
from linked_past_store.void import generate_void

from scripts.pipeline_config import build_annotations, load_dataset_config, render_citation
from scripts.validate_dataset import diff_schemas


def main(dataset: str, version: str = "latest"):
    ds = load_dataset_config(dataset)
    raw_ref = ds["raw_ref"]
    clean_ref = ds["clean_ref"]

    # Replace tag if version override provided
    if version != "latest":
        base = clean_ref.rsplit(":", 1)[0]
        clean_ref = f"{base}:{version}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Pull raw artifact and record its digest
        print(f"Pulling raw artifact: {raw_ref}")
        try:
            raw_ttl = pull_dataset(raw_ref, tmpdir / "raw")
        except RuntimeError as e:
            print(f"ERROR: Could not pull raw artifact {raw_ref}: {e}")
            print("Run the ingest script first to push raw data to OCI.")
            sys.exit(1)
        cache = ArtifactCache()
        raw_digest = cache.digest_for(raw_ref) or "unknown"
        print(f"Raw digest: {raw_digest}")

        # Load previous schema for diff (before we overwrite the cache)
        old_schema = {}
        try:
            prev_clean = pull_dataset(clean_ref, tmpdir / "prev")
            prev_schema_path = tmpdir / "prev" / "_schema.yaml"
            if prev_schema_path.exists():
                with open(prev_schema_path) as f:
                    old_schema = yaml.safe_load(f).get("classes", {})
                print("Loaded previous schema for diff")
        except Exception:
            print("No previous clean artifact found (first publish)")

        # Sanitize
        print("Sanitizing...")
        clean_ttl = tmpdir / f"{dataset}.ttl"
        sanitize_result = sanitize_turtle(raw_ttl, clean_ttl)
        print(f"Sanitized: {sanitize_result.fixes_applied} fixes applied")

        # Verify
        verify_result = verify_turtle(clean_ttl)
        if not verify_result.ok:
            print(f"Verification FAILED: {verify_result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {verify_result.triple_count:,} triples")

        # Generate VoID
        citation_text = render_citation(ds.get("citation", ""))
        void = generate_void(
            data_path=clean_ttl,
            dataset_id=dataset,
            title=ds["description"],
            license_uri="",
            source_uri=ds["source_url"],
            citation=citation_text,
            output_path=tmpdir / "_void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Extract schema
        schema = extract_schema(data_path=clean_ttl)
        generate_schemas_yaml(schema, tmpdir / "_schema.yaml")
        print(f"Extracted schema: {len(schema.classes)} classes")

        # Schema diff (run before push, while both schemas are in memory)
        new_schema_path = tmpdir / "_schema.yaml"
        if old_schema and new_schema_path.exists():
            with open(new_schema_path) as f:
                new_schema = yaml.safe_load(f).get("classes", {})
            schema_diff = diff_schemas(old_schema, new_schema)
            print(f"{dataset} schema diff:")
            for name, count in schema_diff["added"]:
                print(f"  + Added class: {name} ({count} properties)")
            for name, old_count, new_count in schema_diff["changed"]:
                delta = new_count - old_count
                sign = "+" if delta > 0 else ""
                print(f"  ~ Changed class {name}: {sign}{delta} properties ({old_count} -> {new_count})")
            for name, count in schema_diff["removed"]:
                print(f"  - Removed class: {name} ({count} properties)  <- WARNING")
            if not schema_diff["added"] and not schema_diff["removed"] and not schema_diff["changed"]:
                print("  No changes.")

        # Push clean artifact
        annotations = {
            **build_annotations(ds, dataset),
            "org.opencontainers.image.version": version,
            "io.github.gillisandrew.linked-past.triples": str(verify_result.triple_count),
            "io.github.gillisandrew.linked-past.raw-digest": raw_digest,
        }

        files_to_push = [clean_ttl, tmpdir / "_void.ttl", tmpdir / "_schema.yaml"]

        digest = push_dataset(clean_ref, files_to_push, annotations=annotations)
        print(f"Pushed clean: {clean_ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: clean_dataset.py <dataset> [version]")
        sys.exit(1)
    dataset = sys.argv[1]
    version = sys.argv[2] if len(sys.argv) > 2 else "latest"
    main(dataset, version)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/clean_dataset.py
git commit -m "feat: add generic clean_dataset.py — sanitize, verify, metadata, push"
```

---

### Task 6: Create `scripts/validate_dataset.py`

Post-push validation: triple count regression check. Also defines `diff_schemas()` which is imported by `clean_dataset.py` for pre-push schema comparison.

**Files:**
- Create: `scripts/validate_dataset.py`
- Create: `scripts/tests/test_validate_dataset.py`

**Note:** Task 5 (`clean_dataset.py`) imports `diff_schemas` from this module, so this task must be completed before Task 5.

- [ ] **Step 1: Write failing test for schema diff logic**

```python
# scripts/tests/test_validate_dataset.py
"""Tests for validate_dataset schema diff logic."""


def test_diff_schemas_no_changes():
    from scripts.validate_dataset import diff_schemas

    old = {"Person": {"label": "Person", "properties": [{"pred": "name"}]}}
    new = {"Person": {"label": "Person", "properties": [{"pred": "name"}]}}
    result = diff_schemas(old, new)
    assert result["added"] == []
    assert result["removed"] == []
    assert result["changed"] == []


def test_diff_schemas_added_class():
    from scripts.validate_dataset import diff_schemas

    old = {"Person": {"label": "Person", "properties": []}}
    new = {
        "Person": {"label": "Person", "properties": []},
        "Office": {"label": "Office", "properties": [{"pred": "title"}]},
    }
    result = diff_schemas(old, new)
    assert result["added"] == [("Office", 1)]
    assert result["removed"] == []


def test_diff_schemas_removed_class():
    from scripts.validate_dataset import diff_schemas

    old = {
        "Person": {"label": "Person", "properties": []},
        "Office": {"label": "Office", "properties": [{"pred": "title"}]},
    }
    new = {"Person": {"label": "Person", "properties": []}}
    result = diff_schemas(old, new)
    assert result["removed"] == [("Office", 1)]
    assert result["added"] == []


def test_diff_schemas_changed_properties():
    from scripts.validate_dataset import diff_schemas

    old = {"Person": {"label": "Person", "properties": [{"pred": "name"}]}}
    new = {"Person": {"label": "Person", "properties": [{"pred": "name"}, {"pred": "age"}]}}
    result = diff_schemas(old, new)
    assert len(result["changed"]) == 1
    assert result["changed"][0] == ("Person", 1, 2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest scripts/tests/test_validate_dataset.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `scripts/validate_dataset.py`**

```python
# scripts/validate_dataset.py
"""Validate a clean dataset: triple count regression check.

Schema diff is handled by clean_dataset.py (which has both old and new schemas
in memory before pushing). This script handles post-push validation only.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from linked_past_store import pull_dataset, verify_turtle

from scripts.pipeline_config import load_dataset_config


def diff_schemas(old: dict, new: dict) -> dict:
    """Compare two schema dicts (class_name → {label, properties}).

    Returns:
        {"added": [(name, prop_count)], "removed": [(name, prop_count)],
         "changed": [(name, old_count, new_count)]}
    """
    old_names = set(old.keys())
    new_names = set(new.keys())

    added = sorted(
        [(name, len(new[name].get("properties", []))) for name in new_names - old_names]
    )
    removed = sorted(
        [(name, len(old[name].get("properties", []))) for name in old_names - new_names]
    )
    changed = []
    for name in sorted(old_names & new_names):
        old_count = len(old[name].get("properties", []))
        new_count = len(new[name].get("properties", []))
        if old_count != new_count:
            changed.append((name, old_count, new_count))

    return {"added": added, "removed": removed, "changed": changed}


def main(dataset: str):
    ds = load_dataset_config(dataset)
    clean_ref = ds["clean_ref"]
    min_triples = ds.get("min_triple_count", 0)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Pull clean artifact
        print(f"Pulling clean artifact: {clean_ref}")
        ttl_path = pull_dataset(clean_ref, tmpdir / "clean")

        # Triple count check
        verify_result = verify_turtle(ttl_path)
        count = verify_result.triple_count
        if min_triples and count < min_triples:
            print(f"FAIL: {dataset} — {count:,} triples (min: {min_triples:,})")
            sys.exit(1)
        print(f"PASS: {dataset} — {count:,} triples (min: {min_triples:,})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_dataset.py <dataset>")
        sys.exit(1)
    main(sys.argv[1])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest scripts/tests/test_validate_dataset.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_dataset.py scripts/tests/test_validate_dataset.py
git commit -m "feat: add validate_dataset.py — triple count regression + schema diff"
```

---

### Task 7: Create CI workflow

**Files:**
- Create: `.github/workflows/clean-datasets.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/clean-datasets.yml
name: Clean Datasets

on:
  workflow_dispatch:
    inputs:
      dataset:
        description: 'Dataset to clean and publish'
        required: true
        type: choice
        options:
          - dprr
          - pleiades
          - periodo
          - nomisma
          - crro
          - ocre
          - edh
          - all
      version:
        description: 'Version tag (default: latest)'
        required: false
        default: 'latest'

jobs:
  clean:
    runs-on: ubuntu-latest
    permissions:
      packages: write
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: uv sync

      - name: Install ORAS CLI
        run: |
          ORAS_VERSION="1.2.2"
          curl -LO "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_amd64.tar.gz"
          tar xzf "oras_${ORAS_VERSION}_linux_amd64.tar.gz"
          sudo mv oras /usr/local/bin/

      - name: Login to GHCR
        run: echo "${{ secrets.GITHUB_TOKEN }}" | oras login ghcr.io -u ${{ github.actor }} --password-stdin

      - name: Clean and validate datasets
        run: |
          VERSION="${{ inputs.version }}"
          DATASET="${{ inputs.dataset }}"

          if [ "$DATASET" = "all" ]; then
            DATASETS=$(uv run python -c "import yaml; print(' '.join(yaml.safe_load(open('datasets.yaml')).keys()))")
          else
            DATASETS="$DATASET"
          fi

          for ds in $DATASETS; do
            echo "=== Cleaning $ds ==="
            uv run python scripts/clean_dataset.py "$ds" "$VERSION"
            echo "=== Validating $ds ==="
            uv run python scripts/validate_dataset.py "$ds"
          done

      - name: Tag as latest
        if: inputs.version != 'latest'
        run: |
          VERSION="${{ inputs.version }}"
          DATASET="${{ inputs.dataset }}"

          if [ "$DATASET" = "all" ]; then
            DATASETS=$(uv run python -c "import yaml; print(' '.join(yaml.safe_load(open('datasets.yaml')).keys()))")
          else
            DATASETS="$DATASET"
          fi

          for ds in $DATASETS; do
            REF=$(uv run python -c "import yaml; print(yaml.safe_load(open('datasets.yaml'))['$ds']['clean_ref'].rsplit(':', 1)[0])")
            oras tag "${REF}:${VERSION}" latest
          done
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/clean-datasets.yml
git commit -m "feat: add clean-datasets.yml CI workflow — clean + validate from raw OCI"
```

---

### Task 8: Delete old scripts and workflow

Remove the replaced files. Only do this after confirming the new pipeline works.

**Files:**
- Delete: `scripts/package_dprr.py`
- Delete: `scripts/package_pleiades.py`
- Delete: `scripts/package_periodo.py`
- Delete: `scripts/package_nomisma.py`
- Delete: `scripts/package_crro.py`
- Delete: `scripts/package_ocre.py`
- Delete: `scripts/package_edh.py`
- Delete: `.github/workflows/update-datasets.yml`

- [ ] **Step 1: Delete old package scripts**

```bash
git rm scripts/package_dprr.py scripts/package_pleiades.py scripts/package_periodo.py scripts/package_nomisma.py scripts/package_crro.py scripts/package_ocre.py scripts/package_edh.py
```

- [ ] **Step 2: Delete old workflow**

```bash
git rm .github/workflows/update-datasets.yml
```

- [ ] **Step 3: Run lint to confirm no broken imports**

Run: `uv run ruff check .`
Expected: All checks passed

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove old package_*.py scripts and update-datasets.yml workflow"
```

---

### Task 9: Update documentation

Update CLAUDE.md and relevant READMEs to reflect the new pipeline.

**Files:**
- Modify: `CLAUDE.md`
- Modify: `packages/linked-past/README.md`

- [ ] **Step 1: Update CLAUDE.md**

In the "## Monorepo Structure" section, add a note about `datasets.yaml`:

After the line `Root `pyproject.toml` is workspace config only.` add:
```
`datasets.yaml` at the root is the single source of truth for all dataset metadata (OCI refs, licenses, citations, validation thresholds).
```

In the "## Architecture (linked-past package)" section, replace the scripts bullet:
```
- One-off data scripts live in `scripts/`, not in the packages.
```
with:
```
- Ingest scripts (`scripts/ingest_*.py`) push raw data to OCI. `scripts/clean_dataset.py` and `scripts/validate_dataset.py` are generic pipeline stages. One-off analysis scripts also live in `scripts/`.
```

- [ ] **Step 2: Update the "Packaging Data for OCI" section in `packages/linked-past/README.md`**

Replace:
```markdown
### Packaging Data for OCI

\`\`\`bash
uv run python scripts/package_dprr.py latest
uv run python scripts/package_pleiades.py latest
# etc.
\`\`\`
```

with:
```markdown
### Data Pipeline

Raw data ingestion (run manually, pushes to `raw/` OCI namespace):
\`\`\`bash
uv run python scripts/ingest_pleiades.py
uv run python scripts/ingest_generic.py crro
# etc.
\`\`\`

Cleaning and publishing (run via CI or locally, pulls from raw, pushes to `datasets/`):
\`\`\`bash
uv run python scripts/clean_dataset.py pleiades
uv run python scripts/validate_dataset.py pleiades
\`\`\`

All dataset metadata (OCI refs, licenses, citations, thresholds) lives in `datasets.yaml` at the repo root.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md packages/linked-past/README.md
git commit -m "docs: update CLAUDE.md and README for new data pipeline"
```

---

### Task 10: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass (existing + new pipeline_config and validate_dataset tests)

- [ ] **Step 2: Run lint**

Run: `uv run ruff check .`
Expected: All checks passed

- [ ] **Step 3: Final commit if any fixups needed**

```bash
git add -A
git commit -m "fix: test/lint fixups for data pipeline"
```
