"""Cheaper starts of git and python3 for a test run on macOS (test-slim-3).

On macOS /usr/bin/git and /usr/bin/python3 are xcrun shims: each start first
finds the Command Line Tools binary, then starts it, about 5 ms more per start
(measured on pc2: git 9.4 ms vs 4.5 ms, python3 23.7 ms vs 19.7 ms). One
agent-start.sh test makes about 35 git and 28 python3 starts. direct_tools()
puts one folder of links to the same binaries (what `xcrun --find` names, so the
very program the shim would start) first on PATH, for this process and every
process it starts.

The CLT python also has a bytecode prefix (sys.pycache_prefix, under
~/Library/Caches/com.apple.python): every temp project of a test adds one
folder there that is never removed (130,000 folders, 5.8 GB on pc2). The
processes this one starts write theirs into the same folder of links instead,
removed when this process ends. Only where that prefix is already set, so no
__pycache__ appears beside a source file where it did not before.

Called by tests/run2.py (main) and tests/scripthelp.py (import); the first call
sets AGENT_TEST_TOOLS and later calls in its children do nothing.
AGENT_TEST_SHIMS=1 keeps the old way.
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile

MARK = "AGENT_TEST_TOOLS"


def direct_tools():
    """The folder now first on PATH, or None when nothing changed."""
    if sys.platform != "darwin" or os.environ.get("AGENT_TEST_SHIMS"):
        return None
    done = os.environ.get(MARK)
    if done and os.path.isdir(done):
        return None
    folder = tempfile.mkdtemp(prefix="agent_test_tools_")
    atexit.register(shutil.rmtree, folder, True)
    linked = False
    for name in ("git", "python3"):
        if shutil.which(name) != "/usr/bin/" + name:
            continue   # not the shim (another install comes first): leave it
        try:
            real = subprocess.run(["xcrun", "--find", name], capture_output=True,
                                  text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if real and os.path.isfile(real) and os.access(real, os.X_OK):
            os.symlink(real, os.path.join(folder, name))
            linked = True
    if linked:
        os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
    if getattr(sys, "pycache_prefix", None) and not os.environ.get("PYTHONPYCACHEPREFIX"):
        os.environ["PYTHONPYCACHEPREFIX"] = os.path.join(folder, "pycache")
    os.environ[MARK] = folder
    return folder
