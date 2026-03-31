"""PeriodO dataset plugin."""

from __future__ import annotations

import logging
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
from linked_past.datasets.base import DatasetPlugin, UpdateInfo, ValidationResult, VersionInfo

logger = logging.getLogger(__name__)

_CONTEXT_DIR = Path(__file__).parent / "context"


class PeriodOPlugin(DatasetPlugin):
    name = "periodo"
    display_name = "PeriodO"
    description = (
        "A gazetteer of scholarly definitions of historical, art-historical, "
        "and archaeological periods. Each period has temporal bounds, spatial "
        "coverage, and provenance from a specific authority."
    )
    citation = (
        "PeriodO, A gazetteer of period definitions for linking "
        "and visualizing data, https://perio.do"
    )
    license = "CC0"
    url = "https://perio.do"
    time_coverage = "All periods (prehistoric through modern)"
    spatial_coverage = "Global"
    oci_dataset = "periodo"
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
            version="latest",
            source_url="https://perio.do",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            triple_count=0,
            rdf_format="turtle",
        )

    def check_for_updates(self) -> UpdateInfo | None:
        return None
