"""YAML context loading and rendering for dataset plugins."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_context_yaml(path: Path) -> dict:
    """Load a YAML context file and return its contents."""
    with open(path) as f:
        return yaml.safe_load(f)


def load_prefixes(context_dir: Path) -> dict[str, str]:
    """Load prefix map from a context directory's prefixes.yaml."""
    return load_context_yaml(context_dir / "prefixes.yaml")["prefixes"]


def load_schemas(context_dir: Path) -> dict:
    """Load class schemas from a context directory's schemas.yaml."""
    return load_context_yaml(context_dir / "schemas.yaml")["classes"]


def load_examples(context_dir: Path) -> list[dict]:
    """Load SPARQL examples from a context directory's examples.yaml."""
    return load_context_yaml(context_dir / "examples.yaml")["examples"]


def load_tips(context_dir: Path) -> list[dict]:
    """Load query tips from a context directory's tips.yaml."""
    return load_context_yaml(context_dir / "tips.yaml")["tips"]


def render_class_summary(schemas: dict) -> str:
    """Render a one-line-per-class summary."""
    lines = []
    for cls_name, cls_data in schemas.items():
        comment = cls_data.get("comment", "")
        lines.append(f"- **{cls_name}** (`{cls_data['uri']}`) — {comment}")
    return "\n".join(lines)


def render_examples(examples: list[dict]) -> str:
    """Render example queries as formatted markdown."""
    sections = []
    for ex in examples:
        section = f"Question: {ex['question']}\n\n```sparql\n{ex['sparql'].strip()}\n```"
        sections.append(section)
    return "\n\n---\n\n".join(sections)


def render_tips(tips: list[dict]) -> str:
    """Render query tips as formatted markdown."""
    sections = []
    for tip in tips:
        sections.append(f"- **{tip['title']}**: {tip['body'].strip()}")
    return "\n\n".join(sections)


def get_cross_cutting_tips(tips: list[dict]) -> list[dict]:
    """Return tips where classes is empty (cross-cutting)."""
    return [t for t in tips if not t.get("classes")]


def get_relevant_tips(tips: list[dict], class_names: set[str], limit: int = 5) -> list[dict]:
    """Return tips whose classes overlap with class_names, sorted by overlap size."""
    scored = []
    for tip in tips:
        tip_classes = set(tip.get("classes", []))
        if not tip_classes:
            continue
        overlap = len(tip_classes & class_names)
        if overlap > 0:
            scored.append((overlap, tip))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [tip for _, tip in scored[:limit]]


def get_relevant_examples(examples: list[dict], class_names: set[str], limit: int = 3) -> list[dict]:
    """Return examples whose classes overlap with class_names, sorted by overlap size."""
    scored = []
    for ex in examples:
        ex_classes = set(ex.get("classes", []))
        if not ex_classes:
            continue
        overlap = len(ex_classes & class_names)
        if overlap > 0:
            scored.append((overlap, ex))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in scored[:limit]]
