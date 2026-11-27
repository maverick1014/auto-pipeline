#!/usr/bin/env python3
"""Auto-update helper for the auto-pipeline marketplace. Stdlib only, never raises.

  agent_update.py apply on|off      set autoUpdate on the marketplace entries
  agent_update.py notice <root>     print an UPDATE line when a newer version is known
  agent_update.py refresh           fetch the latest version into the cache
  agent_update.py sync <folder>...  update the stale plugin scopes this repo uses
  agent_update.py statusline on|off|refresh <plugin root>   the status line entry in Claude Code settings.json
  agent_update.py start ...         the start's python work in one process (agent-start.sh), see start_batch()
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
PLUGIN_ID = "auto-pipeline@auto-pipeline"
LOCK_NAME = ".auto-pipeline-update.lock"
LOCK_FRESH_SECONDS = 600
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


def _conf():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import agent_conf
    return agent_conf


def _installed_entries(cdir):
    d = _load(os.path.join(cdir, "plugins", "installed_plugins.json"))
    try:
        entries = d["plugins"][PLUGIN_ID]
    except Exception:
        return []
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _cache_versions(cdir):
    base = os.path.join(cdir, "plugins", "cache", MARKETPLACE, MARKETPLACE)
    try:
        names = os.listdir(base)
    except Exception:
        return []
    return [n for n in names if parse_version(n)
            and os.path.isfile(os.path.join(base, n, ".claude-plugin", "plugin.json"))]


def _newest(entries, cdir):
    found = [e.get("version") for e in entries] + _cache_versions(cdir)
    found = [v for v in found if parse_version(v)]
    return max(found, key=parse_version) if found else None


def _stale_scopes(entries, folders, newest):
    """[(scope, path or None, old version)] this repo uses that run older than NEWEST."""
    real = [os.path.realpath(f) for f in folders]
    out = []
    for e in entries:
        old, scope = e.get("version"), e.get("scope")
        if not parse_version(old) or parse_version(old) >= parse_version(newest):
            continue
        path = e.get("projectPath")
        if scope == "user":
            item = ("user", None, old)
        elif scope in ("project", "local") and isinstance(path, str) and os.path.realpath(path) in real:
            item = (scope, os.path.realpath(path), old)
        else:
            continue
        if item not in out:
            out.append(item)
    return out


def _command(scope, path):
    cmd = "claude plugin update %s --scope %s" % (PLUGIN_ID, scope)
    return "cd %s && %s" % (path, cmd) if path else cmd


def _stale_line(scope, path, old, new, why):
    where = "%s %s" % (scope, path) if path else scope
    return "STALE SCOPE: %s runs %s, newest %s; %s: %s" % (where, old, new, why, _command(scope, path))


def _run_update(scope, cwd, env):
    """None on success, else the reason text."""
    claude = shutil.which("claude", path=env.get("PATH"))
    if not claude:
        return "claude was not found on PATH"
    try:
        r = subprocess.run([claude, "plugin", "update", PLUGIN_ID, "--scope", scope], cwd=cwd,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env=dict(env), timeout=120)
    except Exception as e:
        return "claude plugin update failed: %s" % e.__class__.__name__
    if r.returncode == 0:
        return None
    detail = (r.stderr or r.stdout or "").strip().splitlines()
    return detail[0] if detail else "claude plugin update exited %d" % r.returncode


def _take_lock(lock):
    """True when this call now holds the lock dir. A fresh one belongs to someone else."""
    try:
        os.mkdir(lock)
        return True
    except FileExistsError:
        pass
    except Exception:
        return False
    try:
        if time.time() - os.stat(lock).st_mtime < LOCK_FRESH_SECONDS:
            return False
        shutil.rmtree(lock, ignore_errors=True)
        os.mkdir(lock)
        return True
    except Exception:
        return False


def _update_all(stale, folders, newest, env, cdir):
    lock = os.path.join(cdir, "plugins", LOCK_NAME)
    if not _take_lock(lock):
        return [_stale_line(s, p, o, newest, "another session is updating") for s, p, o in stale]
    lines = []
    try:
        for scope, path, old in stale:
            why = _run_update(scope, path or folders[0], env)
            if why:
                lines.append(_stale_line(scope, path, old, newest, why))
            elif path:
                lines.append("updated %s %s: %s -> %s, restart to apply" % (scope, path, old, newest))
            else:
                lines.append("updated user: %s -> %s, restart to apply" % (old, newest))
    finally:
        shutil.rmtree(lock, ignore_errors=True)
    return lines


def sync_scopes(folders, env=None):
    """Update the scopes of this repo that run older than the newest installed version.
    Returns the lines to print. Never raises, never writes installed_plugins.json."""
    try:
        env = dict(os.environ if env is None else env)
        folders = [f for f in folders if isinstance(f, str)]
        cdir = claude_dir(env)
        entries = _installed_entries(cdir)
        newest = _newest(entries, cdir)
        stale = _stale_scopes(entries, folders, newest) if newest and folders else []
        if not stale:
            return []
        if _conf().get("auto_update", env) is False:
            return [_stale_line(s, p, o, newest, "auto update is off") for s, p, o in stale]
        return _update_all(stale, folders, newest, env, cdir)
    except Exception:
        return []


# ------------------------------------------------------------------ statusline (agent-settings.sh statusline)

class _SLExit(BaseException):
    """The statusline function ends here: the exit code, what goes to stdout, what goes to stderr."""
    def __init__(self, code=0, out="", err=""):
        BaseException.__init__(self)
        self.code, self.out, self.err = code, out, err


def statusline_run(mode, root):
    """agent-settings.sh statusline on|off|refresh. Returns (exit code, stdout text, stderr text)."""
    try:
        _statusline(mode, root)
    except _SLExit as e:
        return e.code, e.out, e.err
    return 0, "", ""


def _statusline(mode, root):
    ac = _conf()
    n = ac.get("statusline_refresh_sec")
    d = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    path = os.path.join(d, "settings.json")
    refresh = mode == "refresh"
    if refresh:
        cache = os.path.realpath(os.path.join(d, "plugins", "cache")) + "/"
        target = None
        for cand in (root, os.environ.get("CLAUDE_PLUGIN_ROOT") or ""):
            if cand and os.path.realpath(cand).startswith(cache) and os.path.isfile(os.path.join(cand, "bin", "agent-statusline.sh")):
                target = cand
                break
        if target is None:
            raise _SLExit(0)
        root = target
    cmd = '"%s/bin/agent-statusline.sh"' % root

    def done():
        raise _SLExit(0, "" if refresh else "statusline %s: %s\n" % (mode, path))

    def stop(msg):
        if refresh:
            raise _SLExit(0)
        raise _SLExit(1, "", msg + "\n")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except FileNotFoundError:
        if refresh:
            raise _SLExit(0)
        data = {}
    except Exception:
        stop("not changed. %s is not valid JSON, left as it is" % path)
    sl = data.get("statusLine")
    has = "statusLine" in data
    ours = isinstance(sl, dict) and isinstance(sl.get("command"), str) and "/bin/agent-statusline.sh" in sl["command"]
    if has and not ours:
        stop("not changed. the statusLine in %s is not ours, left as it is" % path)
    if mode == "on":
        want = {"type": "command", "command": cmd}
        if n is not None:
            want["refreshInterval"] = n
        if ours and sl == want:
            done()
        data["statusLine"] = want
    elif mode == "off":
        if not has:
            done()
        del data["statusLine"]
    else:
        if not ours:
            raise _SLExit(0)
        if n is not None and sl.get("refreshInterval") == n and sl.get("command") == cmd:
            raise _SLExit(0)
        if n is None and sl.get("command") == cmd:
            raise _SLExit(0)
        sl["command"] = cmd
        if n is not None:
            sl["refreshInterval"] = n
    try:
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".settings.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            try:
                os.chmod(tmp, os.stat(path).st_mode & 0o777)
            except OSError:
                pass
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as e:
        stop("not changed. cannot write %s: %s" % (path, e))
    done()


# ------------------------------------------------------------------ the start's python work in one process

class _MemoSubprocess(object):
    """What agent_conf sees as `subprocess` during the start: a read-only git question (symbolic-ref, rev-parse)
    asked twice is answered the second time from memory, so git is asked once per value."""

    def __init__(self, real):
        self._real = real
        self.known = {}

    def __getattr__(self, name):
        return getattr(self._real, name)

    def run(self, cmd, *args, **kwargs):
        key = None
        if isinstance(cmd, list) and len(cmd) > 3 and cmd[0] == "git" and cmd[1] == "-C" and cmd[3] in ("symbolic-ref", "rev-parse"):
            key = tuple(cmd)
            if key in self.known:
                return self.known[key]
        result = self._real.run(cmd, *args, **kwargs)
        if key is not None:
            self.known[key] = result
        return result


def _section(out, name, body):
    out.append("@@AP:%s@@\n%s" % (name, body))


def start_batch(argv):
    """agent-start.sh's python work, in the order it had as separate calls:

        start <project root> <state dir> <plugin root> <role key> <pid> <flags> <key>,<key>...

    flags: "n" = UPDATE notice, auto update apply and the status line refresh; "w" = the WATCH line and the working
    branch; "t" = takeover (only with "w"). Prints sections, each "@@AP:<name>@@" on a line of its own, then the
    text: migrate, set (key=value lines of the keys), perm ("<mode> (from <where>)"), you, warn, sync, notice,
    watch, wb (the working branch name), prod (its production branch, then yes|no|? : refs/heads/<prod> exists).
    Every part may fail alone; a failed part prints an empty section."""
    out = []
    try:
        project, state_dir, plugin_root, role_key, pid, flags, keys = argv[:7]
    except ValueError:
        return 2
    ac = None
    try:
        ac = _conf()
    except Exception:
        pass
    memo = None
    if ac is not None and hasattr(ac, "subprocess"):
        memo = _MemoSubprocess(ac.subprocess)
        ac.subprocess = memo
    # 1. the old-file move first, so every read below sees the moved values
    body = ""
    try:
        try:
            if ac is None:
                raise ImportError("no agent_conf")
            lines = ac.migrate(project)
        except ImportError:
            lines = []
        except Exception as exc:
            lines = ["SETTINGS: %s" % exc.__class__.__name__]
        body = "".join(line + "\n" for line in lines)
    except Exception:
        body = ""
    _section(out, "migrate", body)
    # 2. the values asked for (a value with a line break stays unread: the caller asks for it alone)
    body = ""
    for key in [k for k in keys.split(",") if k]:
        try:
            value = ac.text(ac.get(key))
        except Exception:
            continue
        if "\n" in value or "\r" in value:
            continue
        body += "%s=%s\n" % (key, value)
    _section(out, "set", body)
    body = ""
    try:
        body = "%s (from %s)\n" % (ac.text(ac.get("permission_mode")), ac.source("permission_mode"))
    except Exception:
        body = ""
    _section(out, "perm", body)
    body = ""
    try:
        try:
            line = ac._you_cli(role_key, pid)
        except Exception:
            line = "YOU: unknown unknown (model: unknown, effort: unknown)"
        body = line + "\n"
    except Exception:
        body = ""
    _section(out, "you", body)
    body = ""
    try:
        body = "".join(w + "\n" for w in ac.warnings() + ac.shared_lines(project))
    except Exception:
        body = ""
    _section(out, "warn", body)
    # 3. the stale plugin scopes
    body = ""
    try:
        body = "".join(line + "\n" for line in sync_scopes([state_dir, project]))
    except Exception:
        body = ""
    _section(out, "sync", body)
    # 4. UPDATE notice, auto update apply, status line refresh
    body = ""
    if "n" in flags:
        try:
            cdir = claude_dir()
            cache = cache_path()
            line = notice_line(plugin_root, cdir, cache)
            if line:
                body = line + "\n"
            if stale(cache) and version_url(cdir) is not None:
                _spawn_refresh()
        except Exception:
            pass
        _section(out, "notice", body)
        try:
            au = ac.text(ac.get("auto_update"))
        except Exception:
            au = ""
        au = au.split(" (from ")[0]
        au = "off" if au == "off" else "on"
        try:
            apply_auto_update(au == "on", claude_dir())
        except Exception:
            pass
        try:
            statusline_run("refresh", plugin_root)
        except Exception:
            pass
    else:
        _section(out, "notice", "")
    # 5. the WATCH line and the working branch
    watch, wb, prod = "", "", ""
    if "w" in flags:
        try:
            import agent_watchfile as w
            line = w.start_line(project, plugin_root, takeover="t" in flags)
            if line:
                watch = line + "\n"
        except Exception:
            watch = ""
        try:
            wb = ac.working_branch(project, derive=True) or ""
            wb = wb.rstrip("\n")
        except Exception:
            wb = ""
        if wb:
            try:
                p = ac.production_branch(project)
                local = "?"
                if memo is not None:
                    key = ("git", "-C", project, "rev-parse", "--verify", "-q", "refs/heads/" + p)
                    if key in memo.known:
                        local = "yes" if memo.known[key].returncode == 0 and memo.known[key].stdout.strip() else "no"
                prod = "%s\n%s\n" % (p, local)
            except Exception:
                prod = ""
    _section(out, "watch", watch)
    _section(out, "wb", wb + "\n" if wb else "")
    _section(out, "prod", prod)
    sys.stdout.write("".join(out))
    return 0


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
        if cmd == "sync":
            for line in sync_scopes(argv[1:]):
                print(line)
            return 0
        sys.stderr.write("usage: agent_update.py apply on|off | notice <plugin_root> | refresh | sync <folder>...\n")
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "statusline":
        _code, _out, _err = statusline_run(sys.argv[2], sys.argv[3])
        sys.stdout.write(_out)
        sys.stderr.write(_err)
        sys.exit(_code)
    if len(sys.argv) >= 2 and sys.argv[1] == "start":
        try:
            code = start_batch(sys.argv[2:])
        except BaseException:
            code = 0
        sys.exit(code)
    try:
        code = main(sys.argv[1:])
    except BaseException:
        code = 0
    sys.exit(code)
