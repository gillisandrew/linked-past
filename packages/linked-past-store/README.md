# linked-past-store

Distribute scholarly RDF datasets as OCI artifacts via container registries like `ghcr.io`. Free, content-addressable, version-tracked storage for linked data.

## Why OCI for Scholarly Data?

Academic linked data projects face a recurring infrastructure problem: RDF datasets need to be hosted, versioned, and distributed reliably, but most projects lack the budget or inclination to run permanent download servers. URLs break, institutions reorganize, grant funding expires — and with it, the data disappears.

OCI (Open Container Initiative) registries solve this by repurposing container infrastructure for arbitrary file distribution:

- **Free hosting** — GitHub Container Registry (`ghcr.io`) provides unlimited free storage for public packages
- **Content-addressable** — Every artifact has a SHA256 digest. Citing `ghcr.io/myorg/my-dataset@sha256:abc123...` guarantees you reference the exact bytes, forever. This is stronger than citing a URL that may serve different content tomorrow.
- **Versioned** — Tag artifacts with version numbers (`v4.1`, `2021-12-16`) and a mutable `latest` tag. Consumers can pin to a specific version for reproducibility or follow `latest` for freshness.
- **Annotated** — OCI manifest annotations carry machine-readable metadata: license (SPDX), citation, source URL, dataset description. No sidecar files needed.
- **Standard tooling** — `oras` CLI and `oras-py` library work with any OCI-compliant registry (ghcr.io, Docker Hub, AWS ECR, etc.)
- **Cacheable** — OCI clients cache layers by digest. Pull once, verify by hash, never re-download unchanged data.

### Content Addressability in Scholarly Context

When you publish a paper citing a dataset, the citation should be *reproducible* — a reader should be able to obtain the exact same data you used. Traditional URL citations fail this test: the server may be down, the file may have been updated, the institution may have reorganized its URLs.

OCI digests solve this. A reference like:

```
ghcr.io/gillisandrew/linked-past/dprr@sha256:2aeecdfd3d99...
```

Is a cryptographic commitment to specific bytes. Any OCI registry serving this digest must serve the same content. The digest is computed from the artifact manifest, which includes the content hashes of all layers. This is the same guarantee that software supply chain security relies on.

For scholarly citation, include both the human-readable tag and the digest:

```
DPRR RDF dataset v1.3.0 (ghcr.io/gillisandrew/linked-past/dprr:1.3.0,
digest sha256:2aeecdfd3d99...). CC BY-NC 4.0.
```

### Manifest Annotations

Each artifact carries metadata in OCI annotations:

| Annotation | Purpose | Example |
|---|---|---|
| `org.opencontainers.image.licenses` | SPDX license identifier | `CC-BY-NC-4.0` |
| `org.opencontainers.image.source` | Upstream project URL | `https://romanrepublic.ac.uk` |
| `org.opencontainers.image.description` | Human-readable description | `Digital Prosopography of the Roman Republic` |
| `org.opencontainers.image.version` | Version tag | `1.3.0` |
| `io.github.gillisandrew.linked-past.citation` | Scholarly citation | `Broughton, MRR I-III` |
| `io.github.gillisandrew.linked-past.source-url` | Original data download URL | `https://example.org/data.ttl` |
| `io.github.gillisandrew.linked-past.format` | RDF serialization format | `text/turtle` |

## Installation

```bash
pip install linked-past-store
```

Or with uv:

```bash
uv add linked-past-store
```

## Usage

### Push a dataset

```python
from linked_past_store import push_dataset

push_dataset(
    ref="ghcr.io/myorg/my-dataset:v1.0",
    path="my_data.ttl",
    annotations={
        "org.opencontainers.image.licenses": "CC-BY-4.0",
        "org.opencontainers.image.source": "https://example.org",
        "io.github.gillisandrew.linked-past.citation": "Smith et al. (2024)",
    },
)
```

### Pull a dataset

```python
from linked_past_store import pull_dataset

path = pull_dataset(
    ref="ghcr.io/myorg/my-dataset:v1.0",
    output_dir="/tmp/data",
)
# path = Path("/tmp/data/my_data.ttl")
```

### Sanitize RDF for strict parsers

Upstream RDF datasets often contain syntax issues that lenient parsers accept but strict parsers (like Oxigraph) reject. Common problems:

- BCP 47 language tag violations (subtags > 8 characters)
- IRIs missing schemes (`doi.org/...` instead of `https://doi.org/...`)
- Invalid characters in Turtle local names
- Invalid Unicode code points in IRIs

```python
from linked_past_store import sanitize_turtle

clean_path = sanitize_turtle(
    input_path="raw_data.ttl",
    output_path="clean_data.ttl",
    # Returns a report of fixes applied
)
```

### Verify with Oxigraph

```python
from linked_past_store import verify_turtle

result = verify_turtle("clean_data.ttl")
print(f"{result.triple_count} triples, {result.errors} errors")
```

### CLI

```bash
# Push
linked-past-store push ghcr.io/myorg/dataset:v1.0 data.ttl --license CC-BY-4.0

# Pull
linked-past-store pull ghcr.io/myorg/dataset:v1.0 --output ./data/

# Sanitize
linked-past-store sanitize raw.ttl --output clean.ttl

# Verify
linked-past-store verify clean.ttl

# Inspect annotations
linked-past-store inspect ghcr.io/myorg/dataset:v1.0
```

## How It Works

```
Your RDF data (Turtle, RDF/XML, JSON-LD)
        │
        ▼
   Sanitize (fix syntax issues for strict parsers)
        │
        ▼
   Verify (load into Oxigraph, confirm triple count)
        │
        ▼
   Push to OCI registry (oras)
   ├── Layer: your_data.ttl (application/x-turtle)
   ├── Annotations: license, citation, source, version
   └── Digest: sha256:... (content-addressable)
        │
        ▼
   Pull from anywhere (oras)
   ├── Cached by digest (never re-download unchanged data)
   └── Verify integrity (hash check on pull)
```

## Supported Registries

Any OCI-compliant registry works:

- **ghcr.io** (GitHub) — free for public packages, recommended
- **Docker Hub** — free tier available
- **AWS ECR** — for private/institutional use
- **Google Artifact Registry** — for GCP users
- **Azure Container Registry** — for Azure users

## License

MIT. Dataset licenses are declared in OCI manifest annotations — this package is the distribution mechanism, not the data itself.
