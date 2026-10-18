"""procs.run_bounded always returns, even when the program it runs has started a child that outlives it (what a launcher
such as piper.exe does on Windows, and what made subprocess.run's own timeout hang forever there)."""
import os
import subprocess
import sys
import time

import pytest

from blaze import procs

# A parent that starts a long-lived child and then waits, like a launcher that runs the real program.
LAUNCHER = (
    "import subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "open(sys.argv[1], 'w').write(str(child.pid))\n"
    "print('started', flush=True)\n"
    "time.sleep(120)\n"
)


def _alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # a killed child that nobody has waited for yet is a zombie: gone for our purposes
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split(") ", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def test_a_program_that_finishes_returns_its_output_and_status():
    r = procs.run_bounded([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"], 30)
    assert (r.returncode, r.stdout.strip(), r.stderr.strip()) == (3, "out", "err")


def test_text_is_passed_in_and_comes_back_in_any_language():
    code = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"
    text = "Hello, élan — 你好"
    assert procs.run_bounded([sys.executable, "-c", code], 30, input=text).stdout == text


def test_a_program_that_cannot_start_is_an_oserror_as_with_subprocess_run():
    with pytest.raises(OSError):
        procs.run_bounded(["this-program-does-not-exist-blaze"], 5)


def test_a_launcher_whose_child_keeps_running_is_stopped_with_its_child(tmp_path):
    pidfile = tmp_path / "child.pid"
    t0 = time.time()
    with pytest.raises(subprocess.TimeoutExpired) as e:
        procs.run_bounded([sys.executable, "-c", LAUNCHER, str(pidfile)], 3)
    assert time.time() - t0 < 30, "it must return soon after the limit, not wait for the child"
    assert "started" in (e.value.output or ""), "what the program had printed so far is kept"
    child = int(pidfile.read_text())
    for _ in range(50):
        if not _alive(child):
            break
        time.sleep(0.2)
    assert not _alive(child), "the child the launcher started must be stopped too"
