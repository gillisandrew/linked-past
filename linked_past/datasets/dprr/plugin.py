"""DPRR dataset plugin."""

from __future__ import annotations

import logging
import os
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from linked_past.core.context import (
    get_cross_cutting_tips,
    get_relevant_examples,
    get_relevant_tips,
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
    render_class_summary,
    render_examples,
    render_tips,
)
from linked_past.core.validate import build_schema_dict, extract_query_classes, validate_semantics
from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo

logger = logging.getLogger(__name__)

_CONTEXT_DIR = Path(__file__).parent / "context"
_DEFAULT_DATA_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"


class DPRRPlugin(DatasetPlugin):
    name = "dprr"
    display_name = "Digital Prosopography of the Roman Republic"
    description = (
        "A structured prosopography of the political elite of the Roman Republic "
        "(c. 509-31 BC), documenting persons, office-holdings, family relationships, "
        "and social status with full source citations."
    )
    citation = (
        "Sherwin et al., Digital Prosopography of the Roman Republic, "
        "romanrepublic.ac.uk"
    )
    license = "CC BY-NC 4.0"
    url = "https://romanrepublic.ac.uk"
    time_coverage = "509-31 BC"
    spatial_coverage = "Roman Republic"

    def __init__(self):
        self._prefixes = load_prefixes(_CONTEXT_DIR)
        self._schemas = load_schemas(_CONTEXT_DIR)
        self._examples = load_examples(_CONTEXT_DIR)
        self._tips = load_tips(_CONTEXT_DIR)
        self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
        for ex in self._examples:
            ex["classes"] = extract_query_classes(ex["sparql"], self._schema_dict)

    def fetch(self, data_dir: Path) -> Path:
        url = os.environ.get("DPRR_DATA_URL", _DEFAULT_DATA_URL)
        logger.info("Downloading DPRR data from %s", url)
        print(f"Downloading DPRR data from {url} ...", file=sys.stderr)

        try:
            tmp_path, _ = urllib.request.urlretrieve(url)
        except OSError as e:
            raise RuntimeError(f"Failed to download data from {url}: {e}") from e

        try:
            with tarfile.open(tmp_path, "r:gz") as tar:
                members = tar.getnames()
                if "dprr.ttl" not in members:
                    raise RuntimeError(f"Tarball does not contain dprr.ttl. Found: {members}")
                tar.extract("dprr.ttl", path=str(data_dir), filter="data")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        result = data_dir / "dprr.ttl"
        print(f"Extracted dprr.ttl to {result}", file=sys.stderr)
        return result

    # load() uses default implementation from ABC (Turtle format)

    def get_prefixes(self) -> dict[str, str]:
        return self._prefixes

    def build_schema_dict(self) -> dict:
        return self._schema_dict

    def get_schema(self) -> str:
        prefix_lines = "\n".join(f"PREFIX {k}: <{v}>" for k, v in self._prefixes.items())
        class_summary = render_class_summary(self._schemas)
        cross_tips = get_cross_cutting_tips(self._tips)
        tips_md = render_tips(cross_tips)
        return (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )

    def validate(self, sparql: str) -> ValidationResult:
        errors = validate_semantics(sparql, self._schema_dict)
        if errors:
            return ValidationResult(valid=False, sparql=sparql, errors=errors)
        return ValidationResult(valid=True, sparql=sparql)

    def get_relevant_context(self, sparql: str) -> str:
        classes = extract_query_classes(sparql, self._schema_dict)
        if not classes:
            return ""
        parts: list[str] = []
        tips = get_relevant_tips(self._tips, classes)
        if tips:
            parts.append(f"## Relevant Tips\n\n{render_tips(tips)}")
        examples = get_relevant_examples(self._examples, classes)
        if examples:
            parts.append(f"## Relevant Examples\n\n{render_examples(examples)}")
        if not parts:
            return ""
        return "\n\n---\n\n" + "\n\n".join(parts)

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        url = os.environ.get("DPRR_DATA_URL", _DEFAULT_DATA_URL)
        return VersionInfo(
            version="1.3.0",
            source_url=url,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            triple_count=0,
            rdf_format="turtle",
        )

    def check_for_updates(self):
        return None
