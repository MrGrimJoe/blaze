"""Run a program with a limit that really holds, on Windows too.

`subprocess.run(..., capture_output=True, timeout=N)` does not hold on Windows when the program is a launcher: pip's
`piper.exe` (and any `.bat` or `.cmd` shim) starts the real program as a child. When the time runs out Python kills only
the launcher, then waits for the pipes to close, and the surviving child keeps them open: the call never returns, and a
test run or a build stays stuck until the CI job is killed an hour later.

So here the output goes to temporary files (there is no pipe to wait for), the input comes from a file, and when time runs
out the whole process tree is stopped. `pipeline.py` does the same for the renderer; this is the version the voice engines,
and the tests that probe them, share.
"""
from __future__ import annotations

import os
import signal
import subprocess
import tempfile
from typing import List, Optional


def kill_tree(proc: subprocess.Popen) -> None:
    """Stop a program and everything it started."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def run_bounded(cmd: List[str], timeout: float, input: Optional[str] = None, encoding: str = "utf-8") -> subprocess.CompletedProcess:
    """Like subprocess.run(cmd, capture_output=True, text=True, input=input, timeout=timeout), but it always returns.

    Raises subprocess.TimeoutExpired (with what the program had printed so far) after stopping the whole process tree, and
    OSError when the program cannot be started, exactly as subprocess.run does.
    """
    popen_kw = {"start_new_session": True} if os.name != "nt" else {}
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as stdin:
        if input is not None:
            stdin.write(input.encode(encoding))
            stdin.flush()
            stdin.seek(0)
        proc = subprocess.Popen(cmd, stdout=out, stderr=err, stdin=stdin if input is not None else subprocess.DEVNULL, **popen_kw)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            out.seek(0)
            err.seek(0)
            raise subprocess.TimeoutExpired(cmd, timeout, output=out.read().decode(encoding, "replace"),
                                            stderr=err.read().decode(encoding, "replace")) from None
        out.seek(0)
        err.seek(0)
        return subprocess.CompletedProcess(cmd, proc.returncode, out.read().decode(encoding, "replace"), err.read().decode(encoding, "replace"))
