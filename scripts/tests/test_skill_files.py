"""Guard the layout of project skills under .claude/skills/.

Claude Code only loads a skill whose entry file is named SKILL.md. The
frontmatter rules follow the superpowers writing-skills conventions.
"""

from pathlib import Path

import pytest
import yaml

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "skills"
SKILL_DIRS = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    end = text.index("\n---", 4)
    block = text[4:end]
    assert len(block) <= 1024, f"{path} frontmatter exceeds 1024 characters"
    return yaml.safe_load(block)


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda p: p.name)
def test_skill_dir_has_skill_md(skill_dir):
    assert (skill_dir / "SKILL.md").is_file(), f"{skill_dir.name} has no SKILL.md"


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda p: p.name)
def test_skill_frontmatter(skill_dir):
    fm = _frontmatter(skill_dir / "SKILL.md")
    assert fm["name"] == skill_dir.name
    assert "Use when" in fm["description"]
    assert set(fm) <= {"name", "description"}, f"unexpected frontmatter keys: {set(fm)}"
