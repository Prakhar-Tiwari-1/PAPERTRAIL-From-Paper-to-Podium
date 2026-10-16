"""Runs inside the sandbox subprocess: blocks sockets, restricts writes to cwd, then exec()s the code file.

Usage: python -I _sandbox_runner.py <repo_root> <code_file>
This is the Windows fallback of SPEC §6 (weaker than `unshare -rn`; stated honestly in the README).
"""
import builtins
import os
import socket
import sys

repo_root, code_file = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(repo_root, "src"))  # the papertrail package (src layout)
ARTIFACTS = os.path.realpath(os.getcwd())


def _blocked(*a, **k):
    raise PermissionError("network access is disabled in the sandbox")


for _name in ("socket", "create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex"):
    setattr(socket, _name, _blocked)

_real_open = builtins.open
_WRITE_CHARS = set("wax+")


def _inside(path) -> bool:
    try:
        return os.path.realpath(path).startswith(ARTIFACTS + os.sep) or os.path.realpath(path) == ARTIFACTS
    except Exception:
        return False


def _guarded_open(file, mode="r", *a, **k):
    if isinstance(file, (str, bytes, os.PathLike)) and _WRITE_CHARS & set(mode) and not _inside(file):
        raise PermissionError(f"writes are only allowed under artifacts/: {file!r}")
    return _real_open(file, mode, *a, **k)


builtins.open = _guarded_open
_real_io_open = __import__("io").open
__import__("io").open = _guarded_open
for _fn in ("remove", "unlink", "rmdir", "rename", "replace", "mkdir", "makedirs"):
    _orig = getattr(os, _fn)

    def _make(orig, fn):
        def guarded(path, *a, **k):
            if not _inside(path):
                raise PermissionError(f"os.{fn} outside artifacts/ is not allowed: {path!r}")
            return orig(path, *a, **k)

        return guarded

    setattr(os, _fn, _make(_orig, _fn))

src = _real_open(code_file, "r", encoding="utf-8").read()
exec(compile(src, code_file, "exec"), {"__name__": "__main__"})
