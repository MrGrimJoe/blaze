"""Keeps the coupling between Blaze's own code and the desktop studio to the three places STATUS.md says it is."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COUPLED = {"blaze/ai.py", "blaze/ui.py", "blaze/launcher.py"}


def test_only_three_modules_know_the_studio_exists():
    found = set()
    for p in (REPO / "blaze").glob("*.py"):
        code = "\n".join(l for l in p.read_text(encoding="utf-8").splitlines() if not l.strip().startswith(("#", '"""')))
        if re.search(r'studio|"src"\s*/|src\.providers', code, re.I):
            found.add(p.relative_to(REPO).as_posix())
    assert found == COUPLED, f"new coupling to the studio: {sorted(found - COUPLED)}; gone: {sorted(COUPLED - found)} (update docs/STATUS.md too)"


def test_the_parser_compiler_voices_and_looks_never_import_each_others_front_ends():
    for name, banned in {"screenplay.py": ("compiler", "pipeline", "ui", "voice"), "looks.py": ("screenplay", "compiler", "pipeline", "ui"),
                         "voice.py": ("screenplay", "compiler", "pipeline", "ui", "art")}.items():
        text = (REPO / "blaze" / name).read_text(encoding="utf-8")
        for mod in banned:
            assert not re.search(rf"^\s*(from \.{mod} import|from \. import .*\b{mod}\b|import blaze\.{mod})", text, re.M), f"{name} imports {mod}"
