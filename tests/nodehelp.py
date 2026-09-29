"""Pick a Node that has node:sqlite (Node 22.5+) for the relay tests.

The relay tests (tests/relay_harness.mjs, bin/agent-city-relay-dev.mjs)
import node:sqlite. A machine's default node may be older (nvm v20 first on
PATH) while a newer one sits in a common place (/opt/homebrew/bin/node).

    NODE           absolute path of the first node that loads node:sqlite,
                   or None: first every PATH folder in order, then PLACES
    SKIP_REASON    the one reason a relay test gives when NODE is None
    find_node(path=None, places=None)
                   the same search, for a given PATH string and place list
    link_node(folder)
                   put a "node" link to NODE in FOLDER (a test's stub folder,
                   first on PATH), so a script that runs plain `node` gets it
"""

import glob
import os
import subprocess

PROBE = "require('node:sqlite')"


def _version_key(path):
    """~/.nvm/versions/node/v24.1.0/bin/node -> (24, 1, 0); newest sorts first."""
    name = os.path.basename(os.path.dirname(os.path.dirname(path))).lstrip("v")
    parts = []
    for p in name.split("."):
        parts.append(int(p) if p.isdigit() else -1)
    return tuple(parts)


def default_places():
    home = os.path.expanduser("~")
    nvm = sorted(glob.glob(os.path.join(home, ".nvm", "versions", "node", "v*", "bin", "node")),
                 key=_version_key, reverse=True)
    return (["/opt/homebrew/bin/node", "/usr/local/bin/node"] + nvm
            + [os.path.join(home, ".volta", "bin", "node"), "/usr/bin/node"])


def _has_sqlite(node):
    if not (os.path.isfile(node) and os.access(node, os.X_OK)):
        return False
    try:
        r = subprocess.run([node, "-e", PROBE], stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def find_node(path=None, places=None):
    if path is None:
        path = os.environ.get("PATH", "")
    if places is None:
        places = default_places()
    seen = set()
    for cand in [os.path.join(d, "node") for d in path.split(os.pathsep) if d] + list(places):
        full = os.path.realpath(cand)
        if full in seen:
            continue
        seen.add(full)
        if _has_sqlite(cand):
            return os.path.abspath(cand)
    return None


SKIP_REASON = ("needs Node 22.5+ (node:sqlite): no such node on PATH, in /opt/homebrew/bin, "
               "/usr/local/bin, ~/.nvm/versions/node, ~/.volta/bin or /usr/bin")

NODE = find_node()


def link_node(folder):
    target = os.path.join(folder, "node")
    if NODE and not os.path.lexists(target):
        os.symlink(NODE, target)
