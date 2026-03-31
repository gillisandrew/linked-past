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
        # Strip remaining braces (e.g., {Title} -> Title)
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
