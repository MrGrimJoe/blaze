"""
Checks the documentation: every relative link points at something that exists, every screenplay shown in the docs parses, and
the README is the hub it claims to be: every Markdown file in the repository can be reached from it by following links, and it
links every main file (programs, modules, tests, tools, examples, workflows, installer files) directly.

    python tools/check_docs.py          (exit status 1 and a list of problems if anything is wrong)
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def markdown_files():
    skip = {"node_modules", "handoff", "cdrca", ".git"}
    return [p for p in REPO.rglob("*.md") if not (skip & set(p.relative_to(REPO).parts))]


def broken_links():
    bad = []
    for md in markdown_files():
        for m in re.finditer(r"\]\(([^)#\s]+)(#[^)]*)?\)", md.read_text(encoding="utf-8", errors="ignore")):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).resolve().exists():
                bad.append(f"{md.relative_to(REPO)} -> {target}")
    return bad


def screenplay_blocks():
    """Fenced blocks in the docs that are complete screenplays (they start with TITLE:, CAST: or SCENE:)."""
    found = []
    for md in markdown_files():
        for block in re.findall(r"```[a-z]*\n(.*?)```", md.read_text(encoding="utf-8", errors="ignore"), re.S):
            if re.match(r"\s*(TITLE:|CAST:|SCENE:)", block):
                found.append((md.relative_to(REPO), re.sub(r"[ \t]*<-.*", "", block)))     # drop the "<- explanation" notes
    return found


def unparsable_screenplays():
    from blaze.screenplay import ScreenplayError, parse
    bad = []
    for md, block in screenplay_blocks():
        try:
            # a fragment (a few CAST: or SCENE: lines) is checked as if it were followed by one spoken line
            sp = parse(block if re.search(r"^[A-Za-z][A-Za-z0-9 _'.\-]{0,23}(\([^)]*\))?:\s*\S", re.sub(r"^(TITLE|SUBTITLE|CAST|SCENE|BACKDROP):.*$", "", block, flags=re.M), re.M) else block + "\nZED: ok\n")
            if sp.warnings:
                bad.append(f"{md}: warnings {sp.warnings}")
        except ScreenplayError as e:
            bad.append(f"{md}: {e}")
    return bad


def _links_of(md: Path):
    for m in re.finditer(r"\]\(([^)#\s]+)(#[^)]*)?\)", md.read_text(encoding="utf-8", errors="ignore")):
        target = m.group(1)
        if not target.startswith(("http://", "https://", "mailto:")):
            yield (md.parent / target).resolve()


def all_markdown():
    """Every Markdown file that belongs to the repository (CDRCA's included, the packages inside node_modules not)."""
    skip = {"node_modules", "handoff"}
    return [p for p in REPO.rglob("*.md")
            if not (skip & set(p.relative_to(REPO).parts)) and not any(x.startswith(".") and x != ".github" for x in p.relative_to(REPO).parts)]


def must_be_linked_from_readme():
    """The files the README links directly: the main programs, modules, tests, tools, examples, workflows and installer files."""
    out = []
    for pattern in ("blaze.py", "blaze.bat", "blaze_app.pyw", "studio_app.pyw", "requirements.txt", "pytest.ini", "cdrca-lib/atoms.cdrca",
                    "blaze/*.py", "blaze/ui_assets/index.html", "blender/*.py", "tests/*.py", "tools/*.py", "tools/screens/*.py", "tools/screens/*.js",
                    "examples/*", "installer/*.py", "installer/*.iss", "installer/*.ps1", "installer/*.txt", ".github/workflows/*.yml"):
        out += [p for p in REPO.glob(pattern) if p.is_file() and p.name != "__init__.py"]
    return out


def readme_hub_problems():
    readme = REPO / "README.md"
    direct = {t for t in _links_of(readme)}
    problems = []
    reached, todo = {readme.resolve()}, [readme]
    while todo:                                           # every Markdown file must be reachable from the README
        for t in _links_of(todo.pop()):
            if t.suffix == ".md" and t.exists() and t not in reached:
                reached.add(t); todo.append(t)
    for md in all_markdown():
        if md.resolve() not in reached:
            problems.append(f"README.md does not lead to {md.relative_to(REPO).as_posix()} (link it from the README or from a document it links)")
    for f in must_be_linked_from_readme():
        if f.resolve() not in direct:
            problems.append(f"README.md does not link {f.relative_to(REPO).as_posix()}")
    return problems


def main() -> int:
    problems = ([f"broken link: {b}" for b in broken_links()] + [f"screenplay: {b}" for b in unparsable_screenplays()]
                + readme_hub_problems())
    n = len(screenplay_blocks())
    for p in problems:
        print(p)
    print(f"checked {len(markdown_files())} documents and {n} screenplays: {'OK' if not problems else str(len(problems)) + ' problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
