"""tools/ci_report.py: the report a CI job writes, the skip policy, and the combined table."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ci_report", REPO / "tools" / "ci_report.py")
ci = importlib.util.module_from_spec(spec)
sys.modules["ci_report"] = ci
spec.loader.exec_module(ci)

XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="5">
<testcase classname="tests.test_blaze.TestScreenplay" name="test_a" time="0.1"/>
<testcase classname="tests.test_blaze.TestScreenplay" name="test_b" time="0.1"/>
<testcase classname="tests.test_blender" name="test_c"><skipped message="Blender not installed here" type="pytest.skip">x</skipped></testcase>
<testcase classname="tests.test_voices.TestPiper" name="test_d"><skipped message="needs pyttsx3"/></testcase>
%s
</testsuite></testsuites>"""
FAIL = '<testcase classname="tests.test_language" name="test_e"><failure message="assert 1 == 2">trace</failure></testcase>'
ERR = '<testcase classname="tests.test_language" name="test_f"><error message="boom">trace</error></testcase>'


def report(tmp_path, extra="", allow=()):
    f = tmp_path / "r.xml"
    f.write_text(XML % extra, encoding="utf-8")
    return ci.from_junit(f, "Blaze tests", list(allow))


class TestOneReport:
    def test_counts_and_per_file_breakdown(self, tmp_path):
        r = report(tmp_path, allow=["Blender", "pyttsx3"])
        assert (r["passed"], r["skipped"], r["failed"]) == (2, 2, 0)
        assert r["files"]["tests/test_blaze.py"] == {"passed": 2, "failed": 0, "skipped": 0}
        assert r["files"]["tests/test_blender.py"]["skipped"] == 1 and "tests/test_voices.py" in r["files"]
        assert ci.verdict(r) == "ok"

    def test_a_skip_that_is_not_expected_fails_the_job(self, tmp_path):
        r = report(tmp_path, allow=["Blender"])
        assert [s["allowed"] for s in r["skips"]] == [True, False]
        assert r["unexpected_skips"] == ["tests.test_voices.TestPiper::test_d"] and ci.verdict(r) == "UNEXPECTED SKIPS"

    def test_failures_and_errors_both_count_as_failed(self, tmp_path):
        r = report(tmp_path, FAIL + ERR, allow=["Blender", "pyttsx3"])
        assert r["failed"] == 2 and ci.verdict(r) == "FAILED"
        assert {f["message"] for f in r["failures"]} == {"assert 1 == 2", "boom"}

    def test_no_tests_is_a_failure(self, tmp_path):
        f = tmp_path / "e.xml"; f.write_text('<testsuites><testsuite name="pytest" tests="0"/></testsuites>')
        assert ci.verdict(ci.from_junit(f, "x", [])) == "NO TESTS RAN"

    def test_the_markdown_names_every_skip_and_whether_it_was_accepted(self, tmp_path):
        md = ci.markdown_one(report(tmp_path, allow=["Blender"]))
        assert "UNEXPECTED SKIPS" in md and "| `tests/test_blaze.py` | 2 | 0 | 0 |" in md
        assert "Blender not installed here" in md and "**NO**" in md


class TestTap:
    def test_node_output_is_counted(self, tmp_path):
        f = tmp_path / "t.log"
        f.write_text("ok - one\nok - two\nnot ok - three\n\n2 tests passed\n")
        r = ci.from_tap(f, "CDRCA")
        assert (r["passed"], r["failed"]) == (2, 1) and ci.verdict(r) == "FAILED"


class TestCombine:
    def write(self, folder, label, passed=3, failed=0, skipped=0):
        (folder / (label.replace(" ", "_") + ".json")).write_text(json.dumps(
            {"label": label, "passed": passed, "failed": failed, "skipped": skipped, "files": {}, "skips": [], "failures": [], "unexpected_skips": []}))

    def test_all_good(self, tmp_path):
        self.write(tmp_path, "A"); self.write(tmp_path, "B", passed=5)
        text, ok = ci.combine(tmp_path, ["A", "B"])
        assert ok and "| **all runs** | | **8** |" in text

    def test_a_missing_report_fails_the_build(self, tmp_path):
        self.write(tmp_path, "A")
        text, ok = ci.combine(tmp_path, ["A", "Windows voices"])
        assert not ok and "Windows voices | ❌ NO REPORT" in text

    def test_a_failing_run_fails_the_build(self, tmp_path):
        self.write(tmp_path, "A", failed=1)
        assert ci.combine(tmp_path, ["A"])[1] is False


class TestCli:
    def test_pytest_command_writes_json_and_returns_the_verdict(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        (tmp_path / "r.xml").write_text(XML % "")
        out = tmp_path / "o.json"
        assert ci.main(["pytest", str(tmp_path / "r.xml"), "--label", "L", "--out", str(out), "--allow-skip", "Blender", "--allow-skip", "pyttsx3"]) == 0
        assert json.loads(out.read_text())["passed"] == 2
        assert ci.main(["pytest", str(tmp_path / "r.xml"), "--label", "L", "--out", str(out)]) == 1        # skips not allowed

    def test_a_missing_results_file_is_reported_not_crashed_on(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        assert ci.main(["pytest", str(tmp_path / "nope.xml"), "--label", "L", "--out", str(tmp_path / "o.json")]) == 1
        assert "NO RESULTS FILE" in capsys.readouterr().out

    def test_the_summary_file_is_appended_to(self, tmp_path, monkeypatch):
        summary = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        (tmp_path / "r.xml").write_text(XML % "")
        ci.main(["pytest", str(tmp_path / "r.xml"), "--label", "L", "--out", str(tmp_path / "o.json")])
        assert "### L" in summary.read_text(encoding="utf-8")


class TestWindowsConsole:
    def test_symbols_and_non_latin_names_do_not_crash_a_console_that_only_knows_ascii(self, tmp_path):
        """The combined table has check marks, and test names can have any letters; a Windows pipe defaults to a narrow code page."""
        import os
        import subprocess
        (tmp_path / "A.json").write_text(json.dumps({"label": "Blaze tests (windows-latest)", "passed": 1, "failed": 0, "skipped": 1, "files": {},
                                                     "skips": [{"test": "t::test_Zoë_علی", "reason": "needs ≥ 2 voices", "allowed": True}],
                                                     "failures": [], "unexpected_skips": []}, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="ascii", PYTHONUTF8="0")
        r = subprocess.run([sys.executable, str(REPO / "tools" / "ci_report.py"), "combine", str(tmp_path)], capture_output=True, env=env)
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
        assert "✅".encode("utf-8") in r.stdout and "Zoë".encode("utf-8") in r.stdout
