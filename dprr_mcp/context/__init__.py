from pathlib import Path

import yaml

_CONTEXT_DIR = Path(__file__).parent


def load_prefixes() -> dict[str, str]:
    """Load the DPRR prefix map from prefixes.yaml."""
    with open(_CONTEXT_DIR / "prefixes.yaml") as f:
        return yaml.safe_load(f)["prefixes"]


def load_schemas() -> dict:
    """Load the DPRR class schemas from schemas.yaml. Returns the 'classes' dict."""
    with open(_CONTEXT_DIR / "schemas.yaml") as f:
        return yaml.safe_load(f)["classes"]


def load_examples() -> list[dict]:
    """Load the curated SPARQL examples from examples.yaml."""
    with open(_CONTEXT_DIR / "examples.yaml") as f:
        return yaml.safe_load(f)["examples"]


def load_tips() -> list[dict]:
    """Load the query tips from tips.yaml."""
    with open(_CONTEXT_DIR / "tips.yaml") as f:
        return yaml.safe_load(f)["tips"]


def render_schemas_as_shex(schemas: dict) -> str:
    """Render the schema dict as ShEx-style text for LLM context injection."""
    sections = []
    for cls_name, cls_data in schemas.items():
        lines = []
        comment = cls_data.get("comment", "")
        if comment:
            lines.append(f"# {cls_data['label']}: {comment}")
        lines.append(f"{cls_data['uri']} {{")
        for prop in cls_data["properties"]:
            prop_comment = prop.get("comment", "")
            suffix = f"  # {prop_comment}" if prop_comment else ""
            lines.append(f"  {prop['pred']} [ {prop['range']} ] ;{suffix}")
        lines.append("}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def render_examples(examples: list[dict]) -> str:
    """Render the example queries as formatted text for LLM context injection."""
    sections = []
    for ex in examples:
        section = f"Question: {ex['question']}\n\n```sparql\n{ex['sparql'].strip()}\n```"
        sections.append(section)
    return "\n\n---\n\n".join(sections)


def render_tips(tips: list[dict]) -> str:
    """Render the query tips as formatted text for LLM context injection."""
    sections = []
    for tip in tips:
        sections.append(f"- **{tip['title']}**: {tip['body'].strip()}")
    return "\n\n".join(sections)
