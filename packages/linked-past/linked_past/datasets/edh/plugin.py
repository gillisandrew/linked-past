"""EDH (Epigraphic Database Heidelberg) dataset plugin."""

from __future__ import annotations

import logging
from pathlib import Path

from pyoxigraph import RdfFormat, Store

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
from linked_past.datasets.base import DatasetPlugin, UpdateInfo, ValidationResult, VersionInfo

logger = logging.getLogger(__name__)

_CONTEXT_DIR = Path(__file__).parent / "context"


class EDHPlugin(DatasetPlugin):
    name = "edh"
    display_name = "Epigraphic Database Heidelberg (EDH)"
    description = (
        "81,000+ Latin inscriptions from across the Roman Empire with transcriptions, "
        "findspots, dates, and prosopographic data. Includes diplomatic and scholarly "
        "edition texts."
    )
    citation = (
        "Epigraphic Database Heidelberg, https://edh.ub.uni-heidelberg.de/. "
        "CC BY-SA 4.0."
    )
    license = "CC BY-SA 4.0"
    url = "https://edh.ub.uni-heidelberg.de"
    time_coverage = "Antiquity through Late Antiquity"
    spatial_coverage = "Roman Empire"
    oci_dataset = "datasets/edh"
    oci_version = "latest"

    def __init__(self):
        self._prefixes = load_prefixes(_CONTEXT_DIR)
        self._schemas = load_schemas(_CONTEXT_DIR)
        self._hand_written_class_names = set(self._schemas.keys())
        self._examples = load_examples(_CONTEXT_DIR)
        self._tips = load_tips(_CONTEXT_DIR)
        self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
        for ex in self._examples:
            ex["classes"] = extract_query_classes(ex["sparql"], self._schema_dict)

    # fetch() uses default ORAS implementation from base class

    def load(self, store: Store, rdf_path: Path) -> int:
        """Load all Turtle files from the data directory (skipping _* metadata sidecars)."""
        data_dir = rdf_path.parent
        for ttl in sorted(data_dir.glob("*.ttl")):
            if ttl.name.startswith("_"):
                continue
            store.bulk_load(path=str(ttl), format=RdfFormat.TURTLE)
        return len(store)

    def get_prefixes(self) -> dict[str, str]:
        return self._prefixes

    def build_schema_dict(self) -> dict:
        return self._schema_dict

    def get_schema(self) -> str:
        prefix_lines = "\n".join(f"PREFIX {k}: <{v}>" for k, v in self._prefixes.items())
        class_summary = render_class_summary(self._schemas)
        cross_tips = get_cross_cutting_tips(self._tips)
        tips_md = render_tips(cross_tips)
        result = (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )
        from linked_past.core.context import render_auto_detected_summary

        auto_section = render_auto_detected_summary(self._schemas, self._hand_written_class_names)
        if auto_section:
            result += f"\n\n{auto_section}"
        return result

    def validate(self, sparql: str) -> ValidationResult:
        hints = validate_semantics(sparql, self._schema_dict)
        return ValidationResult(valid=True, sparql=sparql, suggestions=hints)

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
        return VersionInfo(
            version=self.oci_version,
            source_url="https://edh.ub.uni-heidelberg.de/",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )

    def check_for_updates(self) -> UpdateInfo | None:
        return None
