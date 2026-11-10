"""Prompts genéricos + perfil del proyecto: los marcadores {{X}} salen de las secciones "# @X" del perfil."""
import re
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
_MARKER = re.compile(r"\{\{(\w+)\}\}")


def sections(profile_text):
    found, current = {}, None
    for line in profile_text.splitlines():
        if line.startswith("# @"):
            current = line[3:].strip().upper()
            found[current] = []
        elif current:
            found[current].append(line)
    return {k: "\n".join(v).strip() for k, v in found.items()}


def render(name, profile_text):
    values = sections(profile_text)
    template = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    missing = sorted(set(_MARKER.findall(template)) - set(values))
    if missing:
        raise ValueError(f"Al perfil le faltan las secciones: {', '.join('# @' + m for m in missing)}")
    return _MARKER.sub(lambda m: values[m.group(1)], template)
