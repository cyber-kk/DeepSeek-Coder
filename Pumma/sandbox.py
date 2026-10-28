#!/usr/bin/env python3
"""Pumma Python runner - executes Python code in a restricted child process.

Safety layers (best effort, for a personal local tool):
  * fresh interpreter: python -I -S  (isolated, no user site, no env)
  * import blocklist:  network / process-spawning / GUI modules are refused
  * os.system / os.popen / os.exec* / os.spawn* / os.fork* are disabled
  * resource limits:   512 MB memory, 10 s CPU, 64 open files, 4 MB files
  * wall-clock kill:   12 s hard timeout
  * output cap:        64 KB per stream
"""

import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time

BOOTSTRAP = r'''
import builtins, sys

BLOCKED = {
    "socket", "subprocess", "ctypes", "multiprocessing", "pty", "http",
    "urllib", "ftplib", "telnetlib", "smtplib", "socketserver", "xmlrpc",
    "webbrowser", "tkinter", "curses", "distutils", "setuptools", "pip",
}
_real = builtins.__import__

def _guard(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root in BLOCKED:
        raise ImportError("Pumma sandbox: the '%s' module is blocked." % root)
    return _real(name, globals, locals, fromlist, level)

builtins.__import__ = _guard

import os as _os
class _PummaBlocked(Exception):
    pass

def _blocked(*a, **k):
    raise _PummaBlocked("Pumma sandbox: this os call is blocked.")

for _name in ("system", "popen", "fork", "forkpty", "execv", "execve", "execvp",
              "execvpe", "spawnl", "spawnle", "spawnv", "spawnve", "posix_spawn"):
    if hasattr(_os, _name):
        setattr(_os, _name, _blocked)

src_path = sys.argv[1]
_code = open(src_path, encoding="utf-8").read()
g = {"__name__": "__main__", "__file__": src_path}
try:
    exec(compile(_code, src_path, "exec"), g)
except ImportError as _e:
    if "Pumma sandbox" in str(_e):
        print(str(_e), file=sys.stderr)
        sys.exit(1)
    raise
except _PummaBlocked as _e:
    print(str(_e), file=sys.stderr)
    sys.exit(1)
'''

MAX_OUTPUT = 64 * 1024
WALL_SECONDS = 12
OUT_FILE_LIMIT = 4 * 1024 * 1024
MEM_LIMIT = 512 * 1024 * 1024


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEM_LIMIT, MEM_LIMIT))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (OUT_FILE_LIMIT, OUT_FILE_LIMIT))
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (96, 96))
    except (ValueError, OSError):
        pass
    os.setsid()  # own process group -> clean kill of the whole tree


def run_python(code):
    workdir = tempfile.mkdtemp(prefix="pumma_run_")
    result = {
        "ok": False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "duration_ms": 0,
        "truncated": False,
    }
    try:
        code_path = os.path.join(workdir, "code.py")
        boot_path = os.path.join(workdir, "_boot.py")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)
        with open(boot_path, "w", encoding="utf-8") as f:
            f.write(BOOTSTRAP)

        env = {"PATH": "/usr/bin:/bin", "HOME": workdir, "PYTHONDONTWRITEBYTECODE": "1"}
        started = time.time()
        proc = subprocess.Popen(
            [sys.executable, "-I", "-S", boot_path, code_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            cwd=workdir,
            env=env,
            preexec_fn=_limits,
        )
        try:
            out, err = proc.communicate(timeout=WALL_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), 9)
            except OSError:
                proc.kill()
            out, err = proc.communicate()
            result["exit_code"] = "timeout"
            result["stderr"] = "Pumma sandbox: execution exceeded %d seconds and was stopped." % WALL_SECONDS
            result["duration_ms"] = int((time.time() - started) * 1000)
            return result

        result["duration_ms"] = int((time.time() - started) * 1000)
        result["exit_code"] = proc.returncode
        stdout = out.decode("utf-8", "replace")
        stderr = err.decode("utf-8", "replace")
        if proc.returncode is not None and proc.returncode < 0:
            sig = -proc.returncode
            reason = "CPU time limit reached" if sig in (9, 24) else "signal %d" % sig
            stderr += "\nPumma sandbox: process terminated (%s)." % reason
        if len(stdout) > MAX_OUTPUT:
            stdout = stdout[:MAX_OUTPUT]
            result["truncated"] = True
        if len(stderr) > MAX_OUTPUT:
            stderr = stderr[:MAX_OUTPUT] + "\n... (output truncated)"
        result["stdout"] = stdout
        result["stderr"] = stderr
        result["ok"] = proc.returncode == 0
        return result
    except Exception as e:  # never let the runner itself crash the server
        result["stderr"] = "Pumma sandbox error: %s" % e
        return result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
