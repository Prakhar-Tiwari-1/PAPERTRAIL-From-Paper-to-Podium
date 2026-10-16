"""python_exec(code): the analyst's only code tool (SPEC §6, CLAUDE.md rule 5).

Isolation:
  * WSL available (env PAPERTRAIL_WSL_DISTRO set): `wsl -d <distro> -- unshare -rn python3 ...` (no network).
  * Otherwise: a Windows subprocess with a stripped environment (no API keys), cwd = artifacts/, 60 s timeout,
    sockets disabled and writes restricted to artifacts/ by tools/_sandbox_runner.py. WEAKER than unshare; stated
    honestly in the README.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from papertrail.paths import ROOT
RUNNER = Path(__file__).resolve().parent / "_sandbox_runner.py"
TIMEOUT_S = 60
MAX_OUT = 6000


def stripped_env(artifacts: Path) -> dict[str, str]:
    """Only what python and matplotlib need. No API keys, no tokens, no proxies."""
    keep = {}
    for k in ("SYSTEMROOT", "SystemRoot", "WINDIR", "PATH", "PATHEXT", "COMSPEC"):
        if k in os.environ:
            keep[k] = os.environ[k]
    keep.update({"TEMP": str(artifacts), "TMP": str(artifacts), "MPLBACKEND": "Agg",
                 "MPLCONFIGDIR": str(artifacts / ".mpl"), "PYTHONIOENCODING": "utf-8"})
    return keep


def python_exec(code: str, artifacts: Path, timeout: int = TIMEOUT_S) -> dict:
    artifacts = Path(artifacts).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    n = len(list(artifacts.glob("_exec_*.py")))
    code_file = artifacts / f"_exec_{n}.py"
    code_file.write_text(code, encoding="utf-8")
    before = {p.name for p in artifacts.iterdir()}

    distro = os.getenv("PAPERTRAIL_WSL_DISTRO")
    if distro:
        wsl_path = subprocess.run(["wsl", "-d", distro, "wslpath", "-a", str(code_file)],
                                  capture_output=True, text=True).stdout.strip()
        cmd = ["wsl", "-d", distro, "--cd", str(artifacts), "--", "env", "-i", "PATH=/usr/bin:/bin",
               "MPLBACKEND=Agg", "unshare", "-rn", "python3", wsl_path]
        env = None
        isolation = "wsl-unshare"
    else:
        cmd = [sys.executable, "-I", str(RUNNER), str(ROOT), str(code_file)]
        env = stripped_env(artifacts)
        isolation = "windows-fallback"
    try:
        p = subprocess.run(cmd, cwd=artifacts, env=env, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        out, err, rc = "", f"timeout after {timeout}s", -1
    new = sorted(p.name for p in artifacts.iterdir() if p.name not in before and not p.name.startswith("_exec_"))
    return {"returncode": rc, "stdout": out[-MAX_OUT:], "stderr": err[-MAX_OUT:], "new_files": new, "isolation": isolation}


def make_tool(artifacts: Path):
    """Bind the sandbox to one run's artifacts dir and return the PydanticAI tool function."""

    def run_python(code: str) -> str:
        """Run Python code in a sandbox (no network, no secrets). Working directory is the artifacts folder.
        Write CSVs and SVGs here. Use `from papertrail.tools.plot_style import apply_style, OKABE_ITO` for plots.
        Returns returncode, stdout, stderr and the list of new files."""
        r = python_exec(code, artifacts)
        return (f"returncode={r['returncode']}\nnew_files={r['new_files']}\n"
                f"stdout:\n{r['stdout']}\nstderr:\n{r['stderr']}")

    return run_python
