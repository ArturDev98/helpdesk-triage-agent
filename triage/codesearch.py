"""Busca en el código (solo lectura) los archivos que más probablemente explican el ticket."""
import os
from pathlib import Path

from triage.similarity import tokens

EXTENSIONS = {".py", ".java", ".kt", ".ts", ".js", ".cs", ".go", ".sql", ".yml", ".yaml"}
SKIP_DIRS = {".git", "node_modules", "target", "dist", "build", ".venv", "__pycache__"}


def candidates(roots, text, module_keywords=(), limit=4, context=6):
    """[(ruta, puntaje, fragmento)] ordenados por coincidencias con el ticket y el módulo."""
    words = set(tokens(text)) | set(tokens(" ".join(module_keywords)))
    found = []
    for root in roots:
        for path in _files(Path(root)):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            hits = [i for i, line in enumerate(lines) if words & set(tokens(line))]
            name_bonus = 3 * len(words & set(tokens(path.stem.replace("_", " "))))
            score = len(hits) + name_bonus
            if score:
                found.append((path, root, score, lines, hits))
    found.sort(key=lambda f: -f[2])
    return [(str(path.relative_to(Path(root).parent)).replace("\\", "/"), score, _snippet(lines, hits, context))
            for path, root, score, lines, hits in found[:limit]]


def _files(root):
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if Path(name).suffix in EXTENSIONS:
                yield Path(folder) / name


def _snippet(lines, hits, context):
    """Las líneas alrededor de las coincidencias, numeradas, sin pasar de ~80 líneas por archivo."""
    keep = sorted({j for i in hits for j in range(max(0, i - context), min(len(lines), i + context + 1))})[:80]
    out, previous = [], None
    for j in keep:
        if previous is not None and j != previous + 1:
            out.append("   …")
        out.append(f"{j + 1:4} {lines[j]}")
        previous = j
    return "\n".join(out)
