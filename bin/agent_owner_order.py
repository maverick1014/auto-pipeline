"""Owner order check: did the owner really type these words? (owner-relay)

Read only. Rules: requirements/owner-relay.md. Python 3.9 stdlib only.
Usage (through agent-owner-order.sh):
  agent_owner_order.py <cwd> <session pid> verify|line [options]
"""

import calendar
import datetime
import glob
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_HOURS = 24
DEFAULT_MIN_CHARS = 20
KIND_ORDER = ["assistant", "tool_result", "compact summary", "peer", "task notification",
              "meta", "system", "other", "agent-typed", "pasted"]
AGENT_HEADER = re.compile(r"\[[^\]\n]*\b(opus|sonnet|haiku|fable)\b[^\]\n]*\]", re.I)
PASTED_CLOSED = re.compile(r"<pasted_content\b[^>]*>.*?</pasted_content>", re.S)
PASTED_OPEN = re.compile(r"<pasted_content\b[^>]*>.*\Z", re.S)


class Usage(Exception):
    pass


def normalise(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def width(text):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def cut_pasted(text):
    return PASTED_OPEN.sub("", PASTED_CLOSED.sub("", text))


def shown(path):
    home = os.path.expanduser("~")
    if home and home != "/" and path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path


# ------------------------------------------------------------------ config

def conf_number(key, default):
    """The fixed constant KEY (agent_conf.CONSTANTS) as a whole number >= 1; DEFAULT when it cannot be read."""
    try:
        import agent_conf
        number = int(agent_conf.get(key))
    except Exception:
        return default
    return number if number >= 1 else default


# ------------------------------------------------------------------ where

def machine_name():
    fake = os.environ.get("AGENT_FAKE_HOST", "")
    if fake:
        return fake
    cmd = ["scutil", "--get", "LocalHostName"] if platform.system() == "Darwin" else ["hostname", "-s"]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def config_homes():
    home = os.path.expanduser("~")
    cands = []
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        cands.append(os.environ["CLAUDE_CONFIG_DIR"])
    cands.append(os.path.join(home, ".claude"))
    cands.extend(sorted(glob.glob(os.path.join(
        home, "Library", "Application Support", "orca", "claude-profiles", "*", "home"))))
    out, seen = [], set()
    for c in cands:
        real = os.path.realpath(c)
        if real not in seen:
            seen.add(real)
            out.append(c)
    return out


def clean_repo(repo):
    repo = os.path.expanduser(repo)
    if len(repo) > 1:
        repo = repo.rstrip("/") or "/"
    return repo


def project_folders(repo):
    names = []
    for p in (repo, os.path.realpath(repo)):
        n = re.sub(r"[^A-Za-z0-9]", "-", p)
        if n not in names:
            names.append(n)
    found, seen = [], set()
    for home in config_homes():
        for n in names:
            d = os.path.join(home, "projects", n)
            if os.path.isdir(d):
                real = os.path.realpath(d)
                if real not in seen:
                    seen.add(real)
                    found.append(d)
    return found


# ------------------------------------------------------------------ lines

def content_parts(msg):
    """(text items joined, tool_result item texts joined, has tool_result item)."""
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, str):
        return content, "", False
    texts, results, has_result = [], [], False
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                texts.append(item["text"])
            elif item.get("type") == "tool_result":
                has_result = True
                c = item.get("content")
                if isinstance(c, str):
                    results.append(c)
                elif isinstance(c, list):
                    results.extend(i["text"] for i in c if isinstance(i, dict)
                                   and i.get("type") == "text" and isinstance(i.get("text"), str))
    return "\n".join(texts), "\n".join(results), has_result


def flag(obj, key):
    value = obj.get(key)
    return value is not None and value is not False


def base_kind(obj, has_result):
    """L2 kinds before agent-typed / pasted; None for an owner-prompt candidate."""
    if obj.get("type") == "assistant":
        return "assistant"
    if "toolUseResult" in obj or has_result:
        return "tool_result"
    if flag(obj, "isCompactSummary"):
        return "compact summary"
    origin = obj.get("origin")
    okind = origin.get("kind") if isinstance(origin, dict) else None
    if okind == "peer":
        return "peer"
    if okind == "task-notification":
        return "task notification"
    if flag(obj, "isMeta"):
        return "meta"
    source = obj.get("promptSource")
    if source in ("system", "sdk"):
        return "system"
    if (not isinstance(origin, dict) or okind != "human" or flag(obj, "isSidechain")
            or source not in ("typed", "queued")):
        return "other"
    return None


def agent_typed(cut_raw):
    for line in cut_raw.split("\n"):
        if line.strip():
            return bool(AGENT_HEADER.search(line)) or line.strip().startswith("OWNER ORDER ")
    return False


TS = re.compile(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d+)?(Z|[+-]\d\d:\d\d)")


def parse_ts(value):
    try:
        m = TS.fullmatch(value)
        if not m:
            return None
        y, mo, d, h, mi, sec = (int(m.group(i)) for i in range(1, 7))
        epoch = calendar.timegm(datetime.datetime(y, mo, d, h, mi, sec).timetuple())
        zone = m.group(7)
        if zone != "Z":
            off = int(zone[1:3]) * 3600 + int(zone[4:6]) * 60
            epoch -= off if zone[0] == "+" else -off
        return epoch
    except Exception:
        return None


def minute_of(epoch):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))


def is_alnum(c):
    return c.isascii() and c.isalnum()


def find_quote(text, quote):
    """Index of the first occurrence with good word edges, else -1 (L14)."""
    start = 0
    while True:
        idx = text.find(quote, start)
        if idx < 0:
            return -1
        end = idx + len(quote)
        ok = not (is_alnum(quote[0]) and idx > 0 and is_alnum(text[idx - 1]))
        if ok and is_alnum(quote[-1]) and end < len(text) and is_alnum(text[end]):
            ok = False
        if ok:
            return idx
        start = idx + 1


def snippet(text, quote):
    idx = find_quote(text, quote)
    start = max(0, idx - 20)
    piece = text[start:start + 80]
    return ("…" if start > 0 else "") + piece + ("…" if start + 80 < len(text) else "")


def search(repo, quote, hours):
    """-> (owner matches in window, owner matches older, other hits, folders)."""
    now = time.time()
    cutoff = now - hours * 3600
    folders = project_folders(repo)
    files = []
    for d in folders:
        for p in glob.glob(os.path.join(glob.escape(d), "*.jsonl")):
            try:
                if os.path.isfile(p) and os.stat(p).st_mtime >= cutoff:
                    files.append((os.stat(p).st_mtime, p))
            except OSError:
                pass
    files.sort(reverse=True)
    owner_in, owner_old, others = {}, [], []
    for mtime, path in files:
        try:
            fh = open(path, "r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for raw in fh:
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(obj, dict) or obj.get("type") not in ("user", "assistant"):
                    continue
                epoch = parse_ts(obj.get("timestamp") or "")
                if epoch is None or epoch > now + 60:
                    continue
                text, results, has_result = content_parts(obj.get("message"))
                full = normalise(text + "\n" + results)
                if find_quote(full, quote) < 0:
                    continue
                kind = base_kind(obj, has_result)
                snip_text = full
                if kind is None:
                    cut = cut_pasted(text)
                    if agent_typed(cut):
                        kind = "agent-typed"
                    else:
                        cut_norm = normalise(cut)
                        if ("<pasted_content" not in cut and "</pasted_content>" not in cut
                                and find_quote(cut_norm, quote) >= 0):
                            kind, snip_text = "owner", cut_norm
                        else:
                            kind = "pasted"
                hit = (epoch, mtime, path, snippet(snip_text, quote))
                if kind == "owner":
                    if epoch >= cutoff:
                        key = minute_of(epoch)
                        old = owner_in.get(key)
                        if old is None or mtime > old[1]:
                            owner_in[key] = hit
                    else:
                        owner_old.append(hit)
                else:
                    others.append((kind,) + hit)
    inside = sorted(owner_in.values(), key=lambda h: (h[0], h[1]), reverse=True)
    return inside, owner_old, others, folders


def article(kinds):
    return "an" if kinds[0][0] in "aeiou" else "a"


def reason(inside_unused, owner_old, others, folders, repo, hours):
    if not folders:
        homes = ", ".join(shown(h) for h in config_homes())
        return "no transcript for %s on this machine (looked in: %s)" % (repo, homes)
    if owner_old:
        newest = max(owner_old, key=lambda h: h[0])
        return "older than %dh (newest %s)" % (hours, minute_of(newest[0]))
    if others:
        kinds = [k for k in KIND_ORDER if any(o[0] == k for o in others)]
        newest = max(others, key=lambda o: (o[1], o[2]))
        return "only in %s %s line (%s %s)" % (article(kinds), ", ".join(kinds),
                                              shown(newest[3]), minute_of(newest[1]))
    return "not found (paraphrased, or typed on another machine?)"


# ------------------------------------------------------------------ args

def parse_args(argv, allowed):
    opts = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a not in allowed:
            raise Usage("unknown option: %s" % a)
        if i + 1 >= len(argv):
            raise Usage("missing value for %s" % a)
        opts[a] = argv[i + 1]
        i += 2
    return opts


def parse_time(value):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
    if m:
        if int(m.group(1)) < 24 and int(m.group(2)) < 60:
            return ("clock", "%02d:%s" % (int(m.group(1)), m.group(2)))
        raise Usage("bad --time: %s" % value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", value):
        try:
            datetime.datetime.strptime(value, "%Y-%m-%d %H:%M")
            return ("full", value)
        except ValueError:
            pass
    raise Usage("bad --time: %s (use HH:MM or \"YYYY-MM-DD HH:MM\")" % value)


def get_quote(opts):
    if "--quote" not in opts:
        raise Usage("missing --quote")
    quote = normalise(opts["--quote"])
    if not quote:
        raise Usage("--quote is empty")
    return quote


def run_common(repo, quote):
    hours = conf_number("owner_order_hours", DEFAULT_HOURS)
    min_chars = conf_number("owner_order_min_chars", DEFAULT_MIN_CHARS)
    w = width(quote)
    if w < min_chars:
        return None, "quote too short (%d < %d)" % (w, min_chars)
    inside, old, others, folders = search(repo, quote, hours)
    if inside:
        return inside, None
    return None, reason(None, old, others, folders, repo, hours)


def verify(argv):
    opts = parse_args(argv, ("--repo", "--quote", "--time", "--machine"))
    if "--repo" not in opts:
        raise Usage("missing --repo")
    if not os.path.expanduser(opts["--repo"]).startswith("/"):
        raise Usage("--repo must be an absolute folder")
    quote = get_quote(opts)
    when = parse_time(opts["--time"]) if "--time" in opts else None
    pre = "OWNER ORDER not verified: "
    if "--machine" in opts and opts["--machine"] != machine_name():
        print("%ssender on another machine (%s, this is %s)" % (pre, opts["--machine"], machine_name()))
        return 1
    repo = clean_repo(opts["--repo"])
    inside, why = run_common(repo, quote)
    if inside is None:
        print(pre + why)
        return 1
    if when:
        kept = [h for h in inside if (minute_of(h[0]) if when[0] == "full" else minute_of(h[0])[11:]) == when[1]]
        if not kept:
            print("%sno owner prompt at %s (found at %s)" % (
                pre, opts["--time"], ", ".join(minute_of(h[0]) for h in inside)))
            return 1
        inside = kept
    if len(inside) > 1:
        print(pre + "several owner prompts hold the quote, pass --time")
        for h in inside:
            print('  %s %s "%s"' % (shown(h[2]), minute_of(h[0]), h[3]))
        return 1
    h = inside[0]
    print("OWNER ORDER verified %s %s" % (shown(h[2]), minute_of(h[0])))
    print('match: "%s"' % h[3])
    return 0


def git_toplevel(folder):
    try:
        out = subprocess.run(["git", "-C", folder, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return out or folder
    except Exception:
        return folder


def model_effort(pid):
    try:
        import agent_conf
        line = agent_conf._you_cli("main_manager", pid)
        m = re.match(r"YOU: (\S+) (\S+) ", line)
        if m:
            return m.group(1), m.group(2)
    except Exception:
        pass
    return "unknown", "unknown"


def line_cmd(cwd, pid, argv):
    opts = parse_args(argv, ("--quote", "--repo"))
    quote = get_quote(opts)
    repo = (clean_repo(os.path.abspath(os.path.expanduser(opts["--repo"])))
            if "--repo" in opts else git_toplevel(cwd))
    inside, why = run_common(repo, quote)
    if inside is None:
        print("OWNER ORDER not found: " + why)
        return 1
    minute = minute_of(inside[0][0])
    machine = machine_name()
    model, effort = model_effort(pid)
    print("OWNER ORDER [%s %s] repo %s · machine %s · typed %s" % (model, effort, repo, machine, minute))
    print('"%s"' % quote)
    print("check: agent-owner-order.sh verify --repo %s --machine %s --time %s --quote %s" % (
        shlex.quote(repo), shlex.quote(machine), shlex.quote(minute), shlex.quote(quote)))
    return 0


CLEAR_TEXTS = ("AUTO CLEAR:", "/clear", "/goal ", "CLEARED:")


def human_quiet(cwd, argv):
    """human-quiet --session <id> --minutes <n> [--repo <folder>]: exit 0 'quiet' or 1 'typed <time>'. Read only."""
    opts = parse_args(argv, ("--session", "--minutes", "--repo"))
    if "--session" not in opts or "--minutes" not in opts:
        raise Usage("human-quiet needs --session and --minutes")
    try:
        minutes = int(opts["--minutes"])
    except ValueError:
        raise Usage("--minutes is a whole number")
    repo = (clean_repo(os.path.abspath(os.path.expanduser(opts["--repo"])))
            if "--repo" in opts else git_toplevel(cwd))
    fake = os.environ.get("AGENT_FAKE_NOW")
    now = time.time()
    if fake:
        try:
            now = time.mktime(time.strptime(fake, "%Y-%m-%d %H:%M"))
        except ValueError:
            pass
    newest = None
    wanted = opts["--session"] + ".jsonl"
    folders = project_folders(repo)
    if not any(os.path.isfile(os.path.join(d, wanted)) for d in folders):
        # a session started in a subfolder lives in another project folder: look in every one (F9)
        for home in config_homes():
            folders += [os.path.dirname(x) for x in
                        glob.glob(os.path.join(glob.escape(home), "projects", "*", glob.escape(wanted)))]
    readable = 0
    for d in folders:
        path = os.path.join(d, opts["--session"] + ".jsonl")
        try:
            fh = open(path, "r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        readable += 1
        with fh:
            for raw in fh:
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(obj, dict) or obj.get("type") != "user":
                    continue
                epoch = parse_ts(obj.get("timestamp") or "")
                if epoch is None or epoch > now + 60:
                    continue
                text, _, has_result = content_parts(obj.get("message"))
                if base_kind(obj, has_result) is not None or agent_typed(cut_pasted(text)):
                    continue
                if normalise(text).startswith(CLEAR_TEXTS):
                    continue
                if newest is None or epoch > newest:
                    newest = epoch
    if not readable:
        print("unknown: no transcript for session %s" % opts["--session"])
        return 2
    if newest is None or minutes <= 0 or now - newest >= minutes * 60:
        print("quiet")
        return 0
    print("typed " + minute_of(newest))
    return 1


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except Exception:
            pass
    if len(argv) < 3:
        sys.stderr.write("usage: agent-owner-order.sh verify|line [options]\n")
        return 2
    cwd, pid, command, rest = argv[0], argv[1], argv[2], argv[3:]
    try:
        if command == "verify":
            return verify(rest)
        if command == "human-quiet":
            return human_quiet(cwd, rest)
        if command == "line":
            return line_cmd(cwd, pid or str(os.getppid()), rest)
        raise Usage("unknown command: %s" % command)
    except Usage as e:
        sys.stderr.write("agent-owner-order.sh: %s\n" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
