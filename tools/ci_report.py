#!/usr/bin/env python3
"""
Turns test output into reports a person can read, and enforces that nothing is silently skipped.

A bare "236 passed" says little. This tool makes each CI job write a small report (counts per test file, every skipped test
with its reason, every failure) and a last job combine them into one table on the run's summary page.

    python tools/ci_report.py pytest reports/pytest.xml --label "Blaze tests (windows-latest)" --out reports/blaze-windows.json \\
        [--allow-skip REGEX ...]            # one report from pytest's --junitxml file
    python tools/ci_report.py tap tests.log --label "CDRCA transpiler" --out reports/cdrca-transpiler.json
                                            # one report from Node test output ("ok - ..." / "not ok - ..." lines)
    python tools/ci_report.py combine reports/ --expect "Blaze tests (windows-latest)" ... [--md ci-report.md]
                                            # one table from every *.json in the folder

The skip policy: a skipped test is allowed only if its reason matches an --allow-skip pattern given for that job, so the
reasons a job may skip are written next to the job in ci.yml. Anything else is "unexpected" and fails the job. A job that must
run a test (a Windows voice, Piper, Blender) therefore cannot quietly skip it. `combine --expect` fails when a report that
should exist is missing, which is what a job that crashed before testing looks like.

Each command appends a Markdown summary to $GITHUB_STEP_SUMMARY when that is set, and always prints it. Exit status is 0 only
when there are no failures, no errors, no unexpected skips and at least one test ran.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List


def _file_of(classname: str, name: str) -> str:
    """tests.test_blaze.TestScreenplay -> tests/test_blaze.py (the file a test lives in)."""
    parts = [p for p in classname.split(".") if p]
    for i, p in enumerate(parts):
        if re.match(r"test_", p) or p.endswith("_test"):
            return "/".join(parts[: i + 1]) + ".py"
    return "/".join(parts) + ".py" if parts else "(unknown)"


def from_junit(path: Path, label: str, allow: List[str]) -> dict:
    root = ET.parse(path).getroot()
    report = {"label": label, "passed": 0, "failed": 0, "skipped": 0, "files": {}, "skips": [], "failures": [], "unexpected_skips": []}
    for case in root.iter("testcase"):
        f = _file_of(case.get("classname", ""), case.get("name", ""))
        row = report["files"].setdefault(f, {"passed": 0, "failed": 0, "skipped": 0})
        test = f"{case.get('classname', '')}::{case.get('name', '')}"
        sk, bad = case.find("skipped"), case.find("failure") if case.find("failure") is not None else case.find("error")
        if bad is not None:
            report["failed"] += 1; row["failed"] += 1
            report["failures"].append({"test": test, "message": (bad.get("message") or bad.text or "")[:300].strip()})
        elif sk is not None:
            reason = (sk.get("message") or sk.text or "").strip()
            report["skipped"] += 1; row["skipped"] += 1
            allowed = any(re.search(p, reason) for p in allow)
            report["skips"].append({"test": test, "reason": reason, "allowed": allowed})
            if not allowed:
                report["unexpected_skips"].append(test)
        else:
            report["passed"] += 1; row["passed"] += 1
    return report


def from_tap(path: Path, label: str) -> dict:
    """Node tests print 'ok - name' per test and 'not ok - name' for a failure."""
    report = {"label": label, "passed": 0, "failed": 0, "skipped": 0, "files": {}, "skips": [], "failures": [], "unexpected_skips": []}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"^ok\b", line):
            report["passed"] += 1
        elif re.match(r"^not ok\b", line):
            report["failed"] += 1
            report["failures"].append({"test": line, "message": ""})
    report["files"][Path(path).name] = {"passed": report["passed"], "failed": report["failed"], "skipped": 0}
    return report


def verdict(r: dict) -> str:
    if r["failed"]:
        return "FAILED"
    if r["unexpected_skips"]:
        return "UNEXPECTED SKIPS"
    if r["passed"] + r["skipped"] == 0:
        return "NO TESTS RAN"
    return "ok"


def markdown_one(r: dict) -> str:
    v = verdict(r)
    out = [f"### {r['label']}", "",
           f"**{v}**: {r['passed']} passed, {r['skipped']} skipped, {r['failed']} failed", ""]
    if r["files"]:
        out += ["| test file | passed | skipped | failed |", "|---|---:|---:|---:|"]
        for f, c in sorted(r["files"].items()):
            out.append(f"| `{f}` | {c['passed']} | {c['skipped']} | {c['failed']} |")
        out.append("")
    if r["skips"]:
        out += ["Skipped tests and why (a skip is only accepted when this job lists its reason as expected):", "",
                "| test | reason | accepted |", "|---|---|:-:|"]
        for s in r["skips"]:
            out.append(f"| `{s['test']}` | {s['reason'][:140]} | {'yes' if s['allowed'] else '**NO**'} |")
        out.append("")
    if r["failures"]:
        out += ["Failures:", ""] + [f"- `{x['test']}` {x['message']}" for x in r["failures"]] + [""]
    return "\n".join(out)


def emit(text: str) -> None:
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def combine(folder: Path, expect: List[str]) -> tuple[str, bool]:
    reports: List[dict] = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("**/*.json"))]
    by_label: Dict[str, dict] = {r["label"]: r for r in reports}
    missing = [e for e in expect if e not in by_label]
    rows = ["| test run | result | passed | skipped | failed |", "|---|---|---:|---:|---:|"]
    ok = not missing
    tp = ts = tf = 0
    for r in sorted(reports, key=lambda x: x["label"]):
        v = verdict(r)
        ok = ok and v == "ok"
        tp += r["passed"]; ts += r["skipped"]; tf += r["failed"]
        rows.append(f"| {r['label']} | {'✅ ' if v == 'ok' else '❌ '}{v} | {r['passed']} | {r['skipped']} | {r['failed']} |")
    for m in missing:
        rows.append(f"| {m} | ❌ NO REPORT (the job did not get as far as testing) | 0 | 0 | 0 |")
    rows.append(f"| **all runs** | | **{tp}** | **{ts}** | **{tf}** |")
    text = ["## Test report", "", f"{len(reports)} test runs reported" + (f", {len(missing)} missing" if missing else "") + ".", ""] + rows + [""]
    skips = [(r["label"], s) for r in reports for s in r["skips"]]
    if skips:
        text += ["<details><summary>Every skipped test, and the reason it is accepted</summary>", "", "| run | test | reason |", "|---|---|---|"]
        text += [f"| {l} | `{s['test']}` | {s['reason'][:140]} |" for l, s in skips]
        text += ["", "</details>", ""]
    return "\n".join(text), ok


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):              # a Windows runner's pipe defaults to a code page that cannot print the table's symbols
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pytest"); p.add_argument("xml"); p.add_argument("--label", required=True); p.add_argument("--out", required=True)
    p.add_argument("--allow-skip", action="append", default=[], metavar="REGEX")
    p = sub.add_parser("tap"); p.add_argument("log"); p.add_argument("--label", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("combine"); p.add_argument("folder"); p.add_argument("--expect", nargs="*", default=[]); p.add_argument("--md")
    a = ap.parse_args(argv)

    if a.cmd == "combine":
        text, ok = combine(Path(a.folder), a.expect)
        emit(text)
        if a.md:
            Path(a.md).write_text(text, encoding="utf-8")
        return 0 if ok else 1

    if a.cmd == "pytest":
        if not Path(a.xml).is_file():
            emit(f"### {a.label}\n\n**NO RESULTS FILE** ({a.xml}): pytest did not get as far as writing one.\n")
            return 1
        r = from_junit(Path(a.xml), a.label, a.allow_skip)
    else:
        if not Path(a.log).is_file():
            emit(f"### {a.label}\n\n**NO LOG** ({a.log}).\n")
            return 1
        r = from_tap(Path(a.log), a.label)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(r, indent=2), encoding="utf-8")
    emit(markdown_one(r))
    return 0 if verdict(r) == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
