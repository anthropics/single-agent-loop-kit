# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""The smallest way to load skills on demand, for a harness that cannot yet.

Only each skill's name and description go into the system prompt. The body is
returned by a tool when the model asks for it. Adapt this to your harness; it is
a pattern to copy, not a library.

    skills = load_skills("skills")
    system_prompt += skills_section(skills)
    tools.append(LOAD_SKILL_TOOL(skills))
    # when the model calls load_skill:  result = read_skill(skills, call.input["name"])
"""

import re
from pathlib import Path


def load_skills(directory: str, skip: tuple[str, ...] = ()) -> dict[str, dict]:
    """Read the name and description from each <directory>/<skill>/SKILL.md.

    `skip` leaves skills out by name. Wire it to an environment variable or a flag so the
    "does this skill do anything" check after a fold needs no code change.
    """
    skills = {}
    root = Path(directory).resolve()
    seen: dict[str, Path] = {}
    for path in sorted(Path(directory).glob("*/SKILL.md")):
        if not path.resolve().is_relative_to(root):   # a symlink must not pull in a file from elsewhere
            raise ValueError(f"Skill {path} points outside {root}.")
        front = re.match(r"---\n(.*?)\n---\n", path.read_text(), re.S)
        meta = dict(re.findall(r"^(\w+):\s*(.+)$", front.group(1), re.M)) if front else {}
        name = meta.get("name", path.parent.name).strip().strip("\"'")
        if name.lower() in seen:   # the name comes from the file, so a new folder could quietly replace a skill
            raise ValueError(f"Two skills are named {name}: {seen[name.lower()]} and {path}.")
        seen[name.lower()] = path
        if name not in skip:
            skills[name] = {"description": meta.get("description", ""), "path": path}
    return skills


def skills_section(skills: dict[str, dict]) -> str:
    """The text to append to the system prompt. It stays the same all session, so it caches."""
    listing = "\n".join(f"- {name}: {skill['description']}" for name, skill in skills.items())
    return f"\n\n## Skills\n\nLoad a skill with load_skill before doing work it covers.\n\n{listing}"


def LOAD_SKILL_TOOL(skills: dict[str, dict]) -> dict:
    return {
        "name": "load_skill",
        "description": "Load the full instructions for one skill. Do this before work the skill covers.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": sorted(skills)}},
            "required": ["name"],
        },
    }


def read_skill(skills: dict[str, dict], name: str) -> str:
    """Run this, and every other tool, only for names you declared to the model."""
    if name not in skills:
        return f"Unknown skill {name}."
    return skills[name]["path"].read_text()
