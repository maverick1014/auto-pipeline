#!/usr/bin/env python3
"""Auto-update helper for the auto-pipeline marketplace. Stdlib only, never raises.

  agent_update.py apply on|off      set autoUpdate on the marketplace entries
  agent_update.py notice <root>     print an UPDATE line when a newer version is known
  agent_update.py refresh           fetch the latest version into the cache
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

MARKETPLACE = "auto-pipeline"
STALE_SECONDS = 86400
BAK = ".bak-auto-pipeline"


def claude_dir(env=None):
    try:
        env = os.environ if env is None else env
        d = env.get("CLAUDE_CONFIG_DIR")
        if d:
            return d
        return os.path.join(env.get("HOME") or os.path.expanduser("~"), ".claude")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".claude")


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _apply_file(path, on, getter):
    """Set autoUpdate on one file. Returns one status line."""
    try:
        if not os.path.isfile(path):
            return "%s: not found" % path
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return "%s: not valid JSON, untouched" % path
        if not isinstance(data, dict):
            return "%s: not a JSON object, untouched" % path
        entry = getter(data)
        if not isinstance(entry, dict):
            return "%s: no %s entry, untouched" % (path, MARKETPLACE)
        if isinstance(entry.get("autoUpdate"), bool) and entry["autoUpdate"] is on:
            return "%s: autoUpdate already %s" % (path, "true" if on else "false")
        if not os.path.lexists(path + BAK):
            shutil.copyfile(path, path + BAK)
        entry["autoUpdate"] = on
        out = json.dumps(data, indent=2, ensure_ascii=False)
        if raw.endswith(b"\n"):
            out += "\n"
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".auto-pipeline-")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(out)
            shutil.copymode(path, tmp)
            os.replace(tmp, path)
            tmp = None
        finally:
            if tmp:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        return "%s: autoUpdate set to %s (backup %s)" % (path, "true" if on else "false", path + BAK)
    except Exception as e:
        return "%s: could not update (%s)" % (path, e.__class__.__name__)


def apply_auto_update(on, cdir):
    on = bool(on)
    lines = []
    try:
        lines.append(_apply_file(
            os.path.join(cdir, "settings.json"), on,
            lambda d: (d.get("extraKnownMarketplaces") or {}).get(MARKETPLACE)
            if isinstance(d.get("extraKnownMarketplaces"), dict) else None))
        lines.append(_apply_file(
            os.path.join(cdir, "plugins", "known_marketplaces.json"), on,
            lambda d: d.get(MARKETPLACE)))
    except Exception:
        pass
    return lines


def parse_version(s):
    try:
        if not isinstance(s, str) or not re.fullmatch(r"\d+(\.\d+)*", s):
            return None
        return tuple(int(p) for p in s.split("."))
    except Exception:
        return None


def _plugin_version(path):
    d = _load(path)
    if isinstance(d, dict) and isinstance(d.get("version"), str):
        return d["version"]
    return None


def installed_version(plugin_root):
    try:
        return _plugin_version(os.path.join(plugin_root, ".claude-plugin", "plugin.json"))
    except Exception:
        return None


def clone_version(cdir):
    try:
        clone = os.path.join(cdir, "plugins", "marketplaces", MARKETPLACE)
        version = _plugin_version(os.path.join(clone, ".claude-plugin", "plugin.json"))
        subject = None
        try:
            r = subprocess.run(
                ["git", "-C", clone, "log", "-1", "--format=%s", "--", ".claude-plugin/plugin.json"],
                capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
            if r.returncode == 0 and r.stdout.strip():
                subject = r.stdout.strip()
        except Exception:
            subject = None
        return (version, subject)
    except Exception:
        return (None, None)


def cache_path():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import agent_conf
    return agent_conf.user_conf_path() + ".latest.json"


def version_url(cdir, env=None):
    try:
        env = os.environ if env is None else env
        u = env.get("AUTO_PIPELINE_VERSION_URL")
        if u:
            return u
        d = _load(os.path.join(cdir, "plugins", "known_marketplaces.json"))
        src = d.get(MARKETPLACE, {}).get("source") if isinstance(d, dict) else None
        if isinstance(src, dict) and src.get("source") == "github" and isinstance(src.get("repo"), str) \
                and re.fullmatch(r"[\w.-]+/[\w.-]+", src["repo"]):
            return "https://raw.githubusercontent.com/%s/HEAD/.claude-plugin/plugin.json" % src["repo"]
    except Exception:
        pass
    return None


def refresh(url, cache, timeout=4, now=None):
    now = time.time() if now is None else now
    version = None
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read(1 << 20).decode("utf-8"))
        if isinstance(data, dict) and isinstance(data.get("version"), str):
            version = data["version"]
    except Exception:
        version = None
    try:
        os.makedirs(os.path.dirname(os.path.abspath(cache)), exist_ok=True)
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump({"checked": now, "version": version}, fh)
    except Exception:
        pass


def stale(cache, now=None):
    try:
        now = time.time() if now is None else now
        d = _load(cache)
        checked = d.get("checked") if isinstance(d, dict) else None
        if isinstance(checked, bool) or not isinstance(checked, (int, float)):
            return True
        return now - checked >= STALE_SECONDS
    except Exception:
        return True


def notice_line(plugin_root, cdir, cache):
    try:
        old = installed_version(plugin_root)
        cv, subject = clone_version(cdir)
        d = _load(cache)
        cached = d.get("version") if isinstance(d, dict) else None
        cands = [v for v in (cv, cached if isinstance(cached, str) else None) if parse_version(v)]
        if not old or not parse_version(old) or not cands:
            return None
        new = max(cands, key=parse_version)
        if parse_version(old) >= parse_version(new):
            return None
        head = "UPDATE: auto-pipeline %s available (you run %s)" % (new, old)
        if cv == new and subject:
            if len(subject) > 80:
                subject = subject[:77] + "..."
            head += ": " + subject
        return head + (". Auto update on: installs by itself within 10 min, then /reload-plugins. "
                       "Off: claude plugin update auto-pipeline@auto-pipeline")
    except Exception:
        return None


def _spawn_refresh():
    try:
        null = subprocess.DEVNULL
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "refresh"],
                         stdin=null, stdout=null, stderr=null, start_new_session=True, close_fds=True)
    except Exception:
        pass


def main(argv):
    try:
        cmd = argv[0] if argv else ""
        if cmd == "apply":
            if len(argv) != 2 or argv[1] not in ("on", "off"):
                sys.stderr.write("usage: agent_update.py apply on|off\n")
                return 2
            for line in apply_auto_update(argv[1] == "on", claude_dir()):
                print(line)
            return 0
        if cmd == "notice":
            if len(argv) < 2:
                return 0
            cdir = claude_dir()
            cache = cache_path()
            line = notice_line(argv[1], cdir, cache)
            if line:
                print(line)
            if stale(cache) and version_url(cdir) is not None:
                _spawn_refresh()
            return 0
        if cmd == "refresh":
            url = version_url(claude_dir())
            if url is not None:
                refresh(url, cache_path())
            return 0
        sys.stderr.write("usage: agent_update.py apply on|off | notice <plugin_root> | refresh\n")
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv[1:])
    except BaseException:
        code = 0
    sys.exit(code)
