"""
Turns folders of screenshots (each with a manifest.json) into one gallery page, README.md, in the root folder.

    python tools/screens/make_gallery.py screens --title "Blaze screens" --note "run 42 on main"

Known folders get friendly names and a fixed order; any other folder is listed after them.
"""
import argparse
import json
from pathlib import Path

SECTIONS = {
    "installer": ("The Windows installer", "Each wizard page of the real installer, captured while it ran."),
    "installed-page": ("The installed app's page (Windows, real Chrome)", "The page served by the installed app, with the bundled Python, Node, ffmpeg and browser."),
    "page": ("The Blaze page", "Every state of the page, captured with a real browser against the running app."),
    "installer-assets": ("The installer's pictures", "The icon and the two pictures the installer wizard shows. The wizard pages themselves are captured on Windows by the Screens workflow."),
    "studio": ("The desktop studio's windows", "The first-run provider window in each state, and the main window."),
}


def build(root: Path, title: str, note: str) -> str:
    folders = [p for p in sorted(root.iterdir()) if p.is_dir() and (p / "manifest.json").is_file()]
    order = {name: i for i, name in enumerate(SECTIONS)}
    folders.sort(key=lambda p: (order.get(p.name, 99), p.name))
    lines, problems, count = [f"# {title}", ""], [], 0
    if note:
        lines += [note, ""]
    body = []
    for folder in folders:
        heading, blurb = SECTIONS.get(folder.name, (folder.name, ""))
        items = json.loads((folder / "manifest.json").read_text(encoding="utf-8-sig"))
        items = [items] if isinstance(items, dict) else items
        body += [f"## {heading}", ""] + ([blurb, ""] if blurb else [])
        for it in items:
            body.append(f"### {it['title']}")
            if it.get("error"):
                problems.append(f"{heading}: {it['title']}: {it['error']}")
                body += [f"**Could not be captured:** `{it['error']}`", ""]
                continue
            count += 1
            body += [f"![{it['title']}]({folder.name}/{it['file']})", ""]
            if it.get("check"):
                body += [f"**What to check:** {it['check']}", ""]
            if it.get("playable") is False:
                body += ["_The video player is black here because the browser used for this capture cannot play H.264. A real Chrome, Edge or Firefox plays it._", ""]
    lines += [f"**{count} screens captured.**" + (f" **{len(problems)} could not be captured:**" if problems else ""), ""]
    lines += [f"- {p}" for p in problems] + ([""] if problems else [])
    lines += ["Contents: " + ", ".join(f"[{SECTIONS.get(f.name, (f.name,))[0]}](#{SECTIONS.get(f.name, (f.name,))[0].lower().replace(' ', '-').replace(',', '').replace('(', '').replace(')', '').replace(chr(39), '')})" for f in folders), ""]
    lines += body
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--title", default="Blaze screens")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    root = Path(a.root)
    text = build(root, a.title, a.note)
    (root / "README.md").write_text(text, encoding="utf-8")
    print(f"wrote {root / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
