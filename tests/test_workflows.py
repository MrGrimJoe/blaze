"""
The GitHub workflow files, checked for the mistakes that only show up on a runner:

  * a bash script on a Windows runner that is not told to use bash (Windows runs PowerShell by default; seen for real);
  * `pytest | tee log` without pipefail, which hides a failing test (only an explicit `shell: bash` turns pipefail on);
  * a bash script with a syntax error;
  * test reports that a job writes under one name and the final job expects under another;
  * a Windows leg that is allowed to skip the system-voice tests it exists to run.

tests/test_installer_and_workflows.py checks the workflows against the installer and the files they use.
"""
import functools
import itertools
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WF_DIR = REPO / ".github" / "workflows"
WORKFLOWS = {p.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(WF_DIR.glob("*.yml"))}
CI = WORKFLOWS["ci.yml"]["jobs"]

BASHISM = re.compile(r"(\bif \[|\$\(|\bfi\b|\bexport \w+=|<<|\[\[ |;\s*then\b|\bfor \w+ in\b|\$\{[A-Za-z_]+[:#%/]|\|\| true|&& break|\bnohup\b|\bset -[eux])")


@functools.lru_cache(maxsize=None)
def working_bash():
    """A bash that really runs, or None. `bash` on a Windows runner is usually C:\\Windows\\System32\\bash.exe, the WSL launcher: with
    no Linux distribution installed it exits with an error and no message for every script, so the first one that answers is
    used, with Git for Windows' own bash looked for first."""
    candidates = []
    if os.name == "nt":
        for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
            if root:
                candidates += [os.path.join(root, "Git", "bin", "bash.exe"), os.path.join(root, "Git", "usr", "bin", "bash.exe"),
                               os.path.join(root, "Programs", "Git", "bin", "bash.exe")]
    candidates.append(shutil.which("bash"))
    for exe in candidates:
        if not exe or not os.path.exists(exe):
            continue
        try:
            r = subprocess.run([exe, "-c", "echo ok"], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0 and r.stdout.strip() == "ok":
            return exe
    return None


def jobs():
    for wf_name, wf in WORKFLOWS.items():
        for job_name, job in wf["jobs"].items():
            if "steps" in job:
                yield wf_name, job_name, job


def systems(job):
    """The operating systems a job runs on (the matrix expanded)."""
    runs_on = str(job["runs-on"])
    if "matrix.os" in runs_on:
        return list(job["strategy"]["matrix"]["os"])
    return [runs_on]


def effective_shell(job, step):
    return step.get("shell") or job.get("defaults", {}).get("run", {}).get("shell")


def run_steps(job):
    return [s for s in job["steps"] if "run" in s]


class TestShells:
    def test_a_bash_script_on_a_windows_runner_says_it_wants_bash(self):
        """A step with no shell on a Windows runner runs in PowerShell. A step that says `shell: pwsh` or `cmd` chose that on purpose."""
        for wf, name, job in jobs():
            if not any("windows" in s for s in systems(job)):
                continue
            for step in run_steps(job):
                if effective_shell(job, step) is None and BASHISM.search(step["run"]):
                    pytest.fail(f"{wf}:{name}: step {step.get('name', step['run'][:40])!r} uses bash syntax but nothing selects bash, "
                                f"so a Windows runner would run it in PowerShell")

    def test_a_pipe_into_tee_runs_under_pipefail(self):
        for wf, name, job in jobs():
            for step in run_steps(job):
                if re.search(r"\|\s*tee\b", step["run"]):
                    assert effective_shell(job, step) == "bash", \
                        f"{wf}:{name}: {step.get('name', '')!r} pipes into tee without an explicit `shell: bash`; without pipefail a failing test would show as a pass"

    @pytest.mark.skipif(not working_bash(), reason="needs a bash that runs (on Windows: Git for Windows' bash, not the WSL launcher)")
    def test_every_bash_step_has_valid_syntax(self, tmp_path):
        bad = []
        for wf, name, job in jobs():
            for i, step in enumerate(run_steps(job)):
                sh = effective_shell(job, step)
                if sh not in (None, "bash") or (sh is None and any("windows" in s for s in systems(job))):
                    continue                                                    # PowerShell / cmd steps cannot be checked here
                script = re.sub(r"\$\{\{.*?\}\}", "X", step["run"])
                script = script.replace("\\\r\n", "\\\n")
                f = tmp_path / f"{wf}-{name}-{i}.sh"
                f.write_text(script, encoding="utf-8")
                r = subprocess.run([working_bash(), "-n", f.as_posix()], capture_output=True, text=True)     # C:/... works in Git bash, C:\\... does not
                if r.returncode:
                    bad.append(f"{wf}:{name}:{step.get('name', i)}: {r.stderr.strip()}")
        assert not bad, "\\n".join(bad)


class TestReports:
    """Every test run writes a report; the last job expects exactly those."""

    TEST_JOBS = ("blaze", "studio", "blender", "piper")

    def labels_written(self):
        out = set()
        for name in self.TEST_JOBS:
            job = CI[name]
            for step in run_steps(job):
                for label in re.findall(r'ci_report\.py (?:pytest|tap) \S+ --label "([^"]+)"', step["run"]):
                    for osname in (systems(job) if "${{ matrix.os }}" in label else [None]):
                        out.add(label.replace("${{ matrix.os }}", osname or ""))
        return out

    def labels_expected(self):
        script = " ".join(s["run"] for s in run_steps(CI["test-report"]))
        return set(re.findall(r'"([^"]+)"', script.split("--expect", 1)[1]))

    def test_the_final_report_expects_exactly_what_the_jobs_write(self):
        assert self.labels_written() == self.labels_expected()

    def test_no_two_test_runs_write_their_report_to_the_same_file(self):
        """The final job downloads every report into one folder (merge-multiple): two runs with the same file name would
        overwrite each other, and the table would be missing one of them (the Windows and macOS runs were, for that)."""
        written = []
        for name in self.TEST_JOBS:
            job = CI[name]
            for step in run_steps(job):
                for out in re.findall(r"ci_report\.py (?:pytest|tap) .*?--out ((?:[^\s$]|\$\{\{ matrix\.os \}\})+)", step["run"]):
                    for osname in (systems(job) or [None]):                    # every system's run writes it, named after the system or not
                        written.append((name, out.replace("${{ matrix.os }}", osname or "")))
        files = [f for _, f in written]
        assert written and len(files) == len(set(files)), sorted(f for f in files if files.count(f) > 1)

    def test_every_test_job_uploads_its_report_and_the_final_job_waits_for_all_of_them(self):
        for name in self.TEST_JOBS:
            uploads = [s for s in CI[name]["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact")]
            assert any(str(u["with"]["name"]).startswith("report-") for u in uploads), name
        assert set(CI["test-report"]["needs"]) == set(self.TEST_JOBS)
        assert CI["test-report"]["if"] == "${{ !cancelled() }}"

    def test_report_steps_run_even_when_the_tests_failed(self):
        for name in self.TEST_JOBS:
            reports = [s for s in run_steps(CI[name]) if "ci_report.py" in s["run"]]
            assert reports and all(s.get("if") == "${{ !cancelled() }}" for s in reports), name

    def test_the_self_diagnosing_log_steps_are_still_there(self):
        for name in self.TEST_JOBS:
            text = " ".join(s["run"] for s in run_steps(CI[name]))
            assert "ci-debug-logs" in text, name


class TestSkipPolicy:
    def allowed(self, job_name, osname):
        job = CI[job_name]
        inc = {i["os"]: i["skips"] for i in job["strategy"]["matrix"].get("include", [])}
        return inc.get(osname, "")

    def test_the_windows_leg_may_not_skip_the_system_voice_tests_it_exists_to_run(self):
        skips = self.allowed("blaze", "windows-latest")
        assert "pyttsx3" not in skips
        install = " ".join(s["run"] for s in run_steps(CI["blaze"]))
        assert "pip install pyttsx3" in install and CI["blaze"]["env"]["BLAZE_REQUIRE_VOICE"] == "1"

    def test_linux_and_mac_may_skip_pyttsx3_but_not_the_things_they_install(self):
        for osname in ("ubuntu-latest", "macos-latest"):
            skips = self.allowed("blaze", osname)
            assert "pyttsx3" in skips and "espeak" not in skips         # espeak-ng is installed on both, so its tests must run

    def test_the_blender_job_may_not_skip_anything(self):
        report = [s for s in run_steps(CI["blender"]) if "ci_report.py" in s["run"]][0]["run"]
        assert "--allow-skip" not in report

    def test_the_piper_job_installs_the_real_piper_and_demands_it(self):
        job = CI["piper"]
        assert job["env"]["BLAZE_REQUIRE_PIPER"] == "1" and "piper-tts" in " ".join(s["run"] for s in run_steps(job))
        assert set(systems(job)) == {"ubuntu-latest", "windows-latest"}
        assert "pyttsx3" not in self.allowed("piper", "windows-latest") and "espeak" not in self.allowed("piper", "ubuntu-latest")

    def test_every_policy_is_a_valid_regular_expression(self):
        for name in ("blaze", "piper"):
            for inc in CI[name]["strategy"]["matrix"]["include"]:
                re.compile(inc["skips"])
