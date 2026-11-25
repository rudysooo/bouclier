"""Tous les fichiers Python doivent au moins se compiler (y compris l'interface de secours)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIPPED = {"build", "dist", "dist_installateur", ".venv", ".venv_build"}
FILES = sorted(p for p in ROOT.rglob("*.py*") if p.suffix in (".py", ".pyw")
               and not SKIPPED & set(p.relative_to(ROOT).parts))


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_source_compiles(path):
    compile(path.read_bytes(), str(path), "exec")
