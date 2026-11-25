#!/usr/bin/env python3
"""agent_state.py - `state add` and `state trim` of bin/agent-file.sh (python3 stdlib only).

Run by agent-file.sh, never by hand:

    agent_state.py <project root> <state dir> <now> add "<line>"
    agent_state.py <project root> <state dir> <now> trim [--dry-run | --auto]

  project root  the main repo: agent_todo.txt, agent_completed.txt
  state dir     the git toplevel of the cwd: agent_state.txt and the day archives
  now           "YYYY-MM-DD HH:MM" (AGENT_FAKE_NOW); empty = the machine clock

--auto is for callers (todo done, housekeep): silent when nothing moved or state_trim_auto=off,
a refusal is one warning line on stderr and the exit stays 0.

Importable by agent_housekeep.py:

    import agent_state
    res = agent_state.trim(root, state_dir, now)   # TrimResult; never raises
    res.kind     "moved" | "nothing" | "refused" | "off"
    res.moved, res.n, res.day_name, res.message
    agent_state.trim_auto_on(root)                  # state_trim_auto != off

Rules: requirements/state-trim.md sections 0, A1, A2, A3. Files are read and written as bytes
(utf-8, errors=surrogateescape), so no byte of a line changes.
"""

import datetime
import fcntl
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent_conf  # noqa: E402

STATE_NAME = "agent_state.txt"
EXCLUDE_LINE = "agent_state.*.txt"
RULES = ["K1", "K2", "K3", "K3b", "K4", "K5", "K6", "K7", "K8", "H", "P"]
MAX_RESTARTS = 3
QUOTES = "\"'`\u201c\u201d\u2018\u2019\u00ab\u00bb\u300c\u300d\u300e\u300f"
WORD_CHARS = "A-Za-z0-9_-"

DEFAULTS = {"state_keep_hours": 24, "state_header_lines": 40}

TRAIL = re.compile(r"(?:^| )\| (\d{4}-\d\d-\d\d \d\d:\d\d)\s*$")
LEAD = re.compile(r"\s*(?:[-*]\s+)?(\d{4}-\d\d-\d\d)(?: (\d\d:\d\d))?(?:\s|$)")
SINCE = re.compile(r"(?:^| \| )since (\d{4}-\d\d-\d\d \d\d:\d\d)")
HEADER_STAMP = re.compile(r"=== .+ (\d{4}-\d\d-\d\d \d\d:\d\d) ===\s*$")
CLEAN_STAMP = re.compile(r"HOUSEKEEP (\d{4}-\d\d-\d\d(?: \d\d:\d\d)?): clean")
LEAD_STRIP = r"^\s*(?:[-*]\s+)?(?:\d{4}-\d\d-\d\d(?: \d\d:\d\d)?\s+)?"
RULE_CARRY = re.compile(LEAD_STRIP + r"(?:RULE(?:[: ]|$)|CARRY(?:[: ]|$))")
HEARTBEAT = re.compile(LEAD_STRIP + r"HEARTBEAT(?:$|[ :])")
HEARTBEAT_TASK = re.compile(LEAD_STRIP + r"HEARTBEAT ([^\s:]+):")
OWNER_LINE = re.compile(LEAD_STRIP + r"OWNER ")
OWNER_TODO = re.compile(r"(?<![%s])OWNER TODO:" % re.escape(QUOTES))
K2_PREFIXES = ("PARKED: ", "QUESTIONS PAGE: ", "STAGE ", "WORKER ", "GOAL:", "LAUNCH ")
TODO_LINE = re.compile(r"\s*TODO LINE:")


class Refuse(Exception):
    pass


class TrimResult(object):
    def __init__(self, kind, message="", moved=0, kept=0, n=0, day_name=""):
        self.kind = kind
        self.message = message
        self.moved = moved
        self.kept = kept
        self.n = n
        self.day_name = day_name


# ---------------------------------------------------------------- small io


def to_text(data):
    return data.decode("utf-8", "surrogateescape")


def to_bytes(text):
    return text.encode("utf-8", "surrogateescape")


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def write_atomic(path, data):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def split_lines(data):
    """The lines of a file, split on \\n only; a last line without a newline still counts."""
    text = to_text(data)
    if text == "":
        return []
    parts = text.split("\n")
    if parts[-1] == "":
        parts.pop()
    return parts


def join_lines(lines):
    return to_bytes("".join(l + "\n" for l in lines))


def now_of(now):
    if now:
        return now
    return os.environ.get("AGENT_FAKE_NOW") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def parse_time(text):
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def conf_int(key):
    """The fixed constant KEY as a whole number; the DEFAULTS one when it cannot be read."""
    try:
        value = int(agent_conf.get(key))
    except Exception:
        return DEFAULTS[key]
    return value if value > 0 else DEFAULTS[key]


def trim_auto_on(root):
    try:
        return agent_conf.get("state_trim_auto") != "off"
    except Exception:
        return True


# ---------------------------------------------------------------- the lock


def lock_path(state_dir):
    """A lock file in the git dir of the state folder (never replaced by tmp + mv, never in the work tree)."""
    try:
        out = subprocess.run(["git", "-C", state_dir, "rev-parse", "--absolute-git-dir"],
                             capture_output=True, text=True, timeout=20)
        if out.returncode == 0 and out.stdout.strip():
            return os.path.join(out.stdout.strip(), "agent_state.lock")
    except Exception:
        pass
    return os.path.join(state_dir, "agent_state.lock")


class Lock(object):
    """One exclusive flock for a trim or a state add. Blocks until it is free."""

    def __init__(self, state_dir):
        self.path = lock_path(state_dir)
        self.fd = None

    def __enter__(self):
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        except OSError:
            if self.fd is not None:
                os.close(self.fd)
            self.fd = None
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
        return False


# ---------------------------------------------------------------- state add


def add(state_dir, now, args, allow_check=False):
    if len(args) != 1:
        raise Refuse("state add: needs exactly one text in quotes (got %d arguments)" % len(args))
    text = args[0]
    if not text.strip():
        raise Refuse("state add: the text is empty")
    if "\n" in text or "\r" in text:
        raise Refuse("state add: the text must not hold a line break")
    if text.startswith("CHECK ") and not allow_check:
        raise Refuse("state add: a CHECK line is written by agent-file.sh check only")
    path = os.path.join(state_dir, STATE_NAME)
    with Lock(state_dir):
        old = read_bytes(path) or b""
        prefix = b"\n" if old and not old.endswith(b"\n") else b""
        with open(path, "ab") as fh:
            fh.write(prefix + to_bytes("%s | %s\n" % (text, now)))
    sys.stdout.write("state add: %s\n" % text[:60])


# ---------------------------------------------------------------- reading the project files


def first_fields(path, index):
    names = []
    data = read_bytes(path)
    if data is None:
        return names
    for line in split_lines(data):
        parts = line.split(" | ")
        if len(parts) > index and parts[index].strip():
            names.append(parts[index].strip())
    return names


def name_regex(names):
    names = sorted(set(names), key=lambda s: (-len(s), s))
    if not names:
        return None
    return re.compile("(?<![%s])(?:%s)(?![%s])" % (WORD_CHARS, "|".join(re.escape(n) for n in names), WORD_CHARS))


# ---------------------------------------------------------------- the rules


def stamp_of(line):
    """(kind, datetime) of the stamp a line carries, or (0, None). Kinds 1-4 are A2.1."""
    m = TRAIL.search(line)
    if m:
        t = parse_time(m.group(1))
        if t:
            return 1, t
    m = LEAD.match(line)
    if m:
        t = parse_time("%s %s" % (m.group(1), m.group(2) or "00:00"))
        if t:
            return 2, t
    m = SINCE.search(line)
    if m:
        t = parse_time(m.group(1))
        if t:
            return 3, t
    m = HEADER_STAMP.match(line)
    if m:
        t = parse_time(m.group(1))
        if t:
            return 4, t
    m = CLEAN_STAMP.match(line)
    if m:
        d = m.group(1)
        t = parse_time(d if " " in d else d + " 00:00")
        if t:
            return 4, t
    return 0, None


def question_scan(lines):
    """Same reading as agent_questions.py worktree_questions().

    Returns (answer, opened): answer[i] = index of the ANSWER line that answers the QUESTION: line i
    (None when it has none), opened = indexes of the open questions (answer None, text not empty).
    """
    answer, opened = {}, []
    for i, line in enumerate(lines):
        if not line.startswith("QUESTION:"):
            continue
        found = None
        for j in range(i + 1, len(lines)):
            later = lines[j]
            if later.startswith("QUESTION:") or later.startswith("=== "):
                break
            if later.lstrip(" ").startswith("ANSWER:"):
                found = j
                break
        answer[i] = found
        if found is None and line[len("QUESTION:"):].strip():
            opened.append(i)
    return answer, opened


def header_end(lines, cap):
    end = 0
    for i in range(min(cap, len(lines))):
        if lines[i].startswith("=== "):
            break
        end = i + 1
        if lines[i].strip() == "":
            break
    return end


def plan(lines, open_re, closed_re, now, keep_hours, header_cap, open_names):
    """One label per line: a rule name (kept) or None (moved)."""
    n = len(lines)
    info = [stamp_of(l) for l in lines]
    when = [None] * n
    below = now
    for i in range(n - 1, -1, -1):
        if info[i][0] == 2:
            when[i] = info[i][1]    # a leading date dates only its own line
            continue
        if info[i][1] is not None:
            below = info[i][1]
        when[i] = below
    limit = now - datetime.timedelta(hours=keep_hours)
    young = [t > limit for t in when]

    lab = [None] * n
    for i in range(header_end(lines, header_cap)):
        lab[i] = "K1"

    def tag(i, rule):
        if lab[i] is None:
            lab[i] = rule

    answer, opened = question_scan(lines)
    k3b = set()
    for i in opened:
        for j in range(i + 1, n):
            if lines[j].startswith("QUESTION:") or lines[j].startswith("=== "):
                k3b.add(j)
                if lines[j].startswith("QUESTION:") and answer.get(j) is not None:
                    k3b.add(answer[j])
                break
    open_set = set(opened)

    k4 = set()
    k4_after = []
    i = 0
    while i < n:
        if lines[i].startswith("=== HOUSEKEEP "):
            k4.add(i)
            j = i + 1
            while j < n and lines[j].startswith("  "):
                k4.add(j)
                j += 1
            if j < n:
                k4_after.append(j)
            i = j
            continue
        if CLEAN_STAMP.match(lines[i]):
            k4.add(i)
        i += 1

    k5 = set()
    i = 0
    while i < n:
        if lines[i].startswith("=== REPORT"):
            j = i + 1
            while j < n and not lines[j].startswith("=== "):
                j += 1
            block = range(i, j)
            if open_re is not None and any(open_re.search(lines[x]) for x in block):
                k5.update(block)
            i = j
            continue
        i += 1

    hb_last = {}
    for i, line in enumerate(lines):
        m = HEARTBEAT_TASK.match(line)
        if m and m.group(1) in open_names and not young[i]:
            hb_last[m.group(1)] = i
    hb_keep = set(hb_last.values())

    for i, line in enumerate(lines):
        if lab[i] is not None:
            continue
        if (RULE_CARRY.match(line) or line.startswith(K2_PREFIXES) or TODO_LINE.match(line)
                or OWNER_TODO.search(line)):
            lab[i] = "K2"
        elif i in open_set:
            lab[i] = "K3"
        elif i in k3b:
            lab[i] = "K3b"
        elif i in k4:
            lab[i] = "K4"
        elif i in k5:
            lab[i] = "K5"
        elif open_re is not None and not HEARTBEAT.match(line) and open_re.search(line):
            lab[i] = "K6"
        elif young[i]:
            lab[i] = "K7"
        elif (OWNER_LINE.match(line) and (open_re is None or not open_re.search(line))
              and (closed_re is None or not closed_re.search(line))):
            lab[i] = "K8"
        elif i in hb_keep:
            lab[i] = "H"
    for q, a in answer.items():
        if a is None:
            continue
        if lab[q] is not None and lab[a] is None:
            lab[a] = "P"
        elif lab[a] is not None and lab[q] is None:
            lab[q] = "P"
    # the line right after a HOUSEKEEP block stays when a kept "  " line follows it: else that line
    # would join the block (and the T3 check would refuse every run)
    for j in k4_after:
        if lab[j] is None and j + 1 < n and lines[j + 1].startswith("  ") and lab[j + 1] is not None:
            lab[j] = "K4"
    return lab


def machine_view(lines):
    """What must be the same before and after a trim (T3)."""
    _, opened = question_scan(lines)
    view = [("open", lines[i]) for i in opened]
    in_block = False
    for line in lines:
        if line.startswith("=== HOUSEKEEP "):
            in_block = True
            view.append(("hk", line))
            continue
        if in_block and line.startswith("  "):
            view.append(("hk", line))
            continue
        in_block = False
        if (line.startswith(K2_PREFIXES) or TODO_LINE.match(line) or OWNER_TODO.search(line)
                or CLEAN_STAMP.match(line)):
            view.append(("m", line))
    return view


def build(root, lines, now):
    open_names = set(first_fields(os.path.join(root, "agent_todo.txt"), 0))
    closed_names = set(first_fields(os.path.join(root, "agent_completed.txt"), 1))
    lab = plan(lines, name_regex(open_names), name_regex(closed_names), parse_time(now) or datetime.datetime.now(),
               conf_int("state_keep_hours"), conf_int("state_header_lines"), open_names)
    return lab


# ---------------------------------------------------------------- trim


def ensure_exclude(state_dir):
    try:
        out = subprocess.run(["git", "-C", state_dir, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                             capture_output=True, text=True, timeout=20)
    except Exception:
        return
    if out.returncode != 0 or not out.stdout.strip():
        return
    path = os.path.join(out.stdout.strip(), "info", "exclude")
    try:
        old = read_bytes(path) or b""
        if EXCLUDE_LINE in [to_text(x).strip() for x in old.split(b"\n")]:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "ab") as fh:
            fh.write((b"\n" if old and not old.endswith(b"\n") else b"") + EXCLUDE_LINE.encode() + b"\n")
    except OSError:
        pass


def cut(line):
    return "  " + line[:100]


def dry_text(lines, lab):
    kept = [l for l, r in zip(lines, lab) if r is not None]
    moved = [l for l, r in zip(lines, lab) if r is None]
    counts = dict((r, 0) for r in RULES)
    for r in lab:
        if r is not None:
            counts[r] += 1
    out = ["state trim (dry run): keep %d, move %d of %d" % (len(kept), len(moved), len(lines)),
           "by rule: " + ", ".join("%s %d" % (r, counts[r]) for r in RULES),
           "first kept:"]
    out += [cut(l) for l in kept[:5]]
    out.append("first moved:")
    out += [cut(l) for l in moved[:5]]
    return "\n".join(out) + "\n"


def check_plan(lines, lab):
    kept = [l for l, r in zip(lines, lab) if r is not None]
    moved = [l for l, r in zip(lines, lab) if r is None]
    if sorted(kept + moved) != sorted(lines) or len(kept) + len(moved) != len(lines):
        raise Refuse("kept and moved lines are not the original lines")
    if machine_view(kept) != machine_view(lines):
        raise Refuse("a machine line or an open question would change")
    return kept, moved


def restore(path, old):
    if old is None:
        if os.path.exists(path):
            os.remove(path)
    else:
        write_atomic(path, old)


def trim(root, state_dir, now, dry_run=False):
    """The whole trim. Never raises: a refusal is TrimResult('refused')."""
    now = now_of(now)
    try:
        if dry_run:
            return _trim(root, state_dir, now, True)
        with Lock(state_dir):
            return _trim(root, state_dir, now, False)
    except Refuse as e:
        return TrimResult("refused", "state trim: refused (%s). Nothing was lost." % e)
    except Exception as e:  # an internal error is a refusal, never a traceback
        return TrimResult("refused", "state trim: refused (%s: %s). Nothing was lost." % (type(e).__name__, e))


def _swap(state_path, kept_bytes, original):
    """Write the new state file (tmp + mv). Bytes another writer put into the old file around the
    swap are appended to the new one. Returns the bytes the new file must start with."""
    old_fh = open(state_path, "rb") if original is not None else None
    late_old = os.environ.get("AGENT_FAKE_TRIM_LATE_OLD")
    second = open(state_path, "ab") if late_old and original is not None else None
    try:
        write_atomic(state_path, kept_bytes)
        if second is not None:
            second.write(to_bytes(late_old + "\n"))
            second.flush()
        grown = b""
        if old_fh is not None:
            old_fh.seek(len(original))
            grown = old_fh.read()
        if grown:
            with open(state_path, "ab") as fh:
                fh.write(grown)
        return kept_bytes + grown
    finally:
        for fh in (old_fh, second):
            if fh is not None:
                fh.close()


def _trim(root, state_dir, now, dry_run):
    state_path = os.path.join(state_dir, STATE_NAME)
    day_name = "agent_state.trim-%s.txt" % now[:10]
    day_path = os.path.join(state_dir, day_name)
    race_left = int(os.environ.get("AGENT_FAKE_TRIM_RACE") or 0)
    race_done = 0
    for attempt in range(MAX_RESTARTS + 1):
        original = read_bytes(state_path)
        lines = split_lines(original or b"")
        n = len(lines)
        if n == 0 and not dry_run:
            return TrimResult("nothing", "state trim: nothing to move (0 lines)", n=0)
        lab = build(root, lines, now)
        if dry_run:
            text = dry_text(lines, lab)
            try:
                check_plan(lines, lab)
            except Refuse as e:
                text += "state trim (dry run): the real run would refuse: %s\n" % e
            return TrimResult("dry", text, n=n)
        kept, moved = check_plan(lines, lab)
        if not moved:
            return TrimResult("nothing", "state trim: nothing to move (%d lines)" % n, kept=n, n=n)
        ensure_exclude(state_dir)
        day_old = read_bytes(day_path)
        hold = os.environ.get("AGENT_FAKE_TRIM_HOLD")
        if hold:
            time.sleep(float(hold))
        sep = b"\n" if day_old and not day_old.endswith(b"\n") else b""
        day_new = (day_old or b"") + sep + join_lines(moved)
        kept_bytes = join_lines(kept)
        write_atomic(day_path, day_new)
        try:
            if race_done < race_left:
                race_done += 1
                with open(state_path, "ab") as fh:
                    fh.write((b"\n" if original and not original.endswith(b"\n") else b"")
                             + ("RACE %d\n" % race_done).encode())
            if read_bytes(state_path) != original:
                restore(day_path, day_old)
                continue
            expect = _swap(state_path, kept_bytes, original)
            late_new = os.environ.get("AGENT_FAKE_TRIM_LATE_NEW")
            if late_new:
                with open(state_path, "ab") as fh:
                    fh.write(to_bytes(late_new + "\n"))
            # another writer's appends after our bytes are fine; anything else is a mismatch
            good = (read_bytes(state_path).startswith(expect) and read_bytes(day_path) == day_new
                    and not os.environ.get("AGENT_FAKE_TRIM_BAD_READBACK"))
            if not good:
                restore(state_path, original if original is not None else b"")
                restore(day_path, day_old)
                raise Refuse("the read-back did not match, both files are back as they were")
        except Refuse:
            raise
        except Exception:
            try:
                restore(state_path, original if original is not None else b"")
                restore(day_path, day_old)
            except OSError:
                pass
            raise
        msg = "state trim: kept %d, moved %d of %d -> %s (checked)" % (len(kept), len(moved), n, day_name)
        return TrimResult("moved", msg, moved=len(moved), kept=len(kept), n=n, day_name=day_name)
    raise Refuse("the state file kept changing while trimming (%d restarts)" % MAX_RESTARTS)


# ---------------------------------------------------------------- command line


def main(argv):
    if len(argv) < 5:
        sys.stderr.write("agent_state.py: needs root state-dir now command\n")
        return 2
    root, state_dir, now, cmd = argv[1], argv[2], now_of(argv[3]), argv[4]
    args = argv[5:]
    try:
        if cmd == "add":
            add(state_dir, now, args)
            return 0
        if cmd == "trim":
            auto = args == ["--auto"]
            if args not in ([], ["--dry-run"], ["--auto"]):
                raise Refuse("state trim: unknown argument: %s (only --dry-run)" % " ".join(args))
            if auto and not trim_auto_on(root):
                return 0
            res = trim(root, state_dir, now, dry_run=args == ["--dry-run"])
            if res.kind == "refused":
                sys.stderr.write(res.message + "\n")
                return 0 if auto else 1
            if auto and res.kind != "moved":
                return 0
            sys.stdout.write(res.message.rstrip("\n") + "\n")
            return 0
        raise Refuse("state: unknown command: %s (add or trim)" % cmd)
    except Refuse as e:
        sys.stderr.write("%s\n" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
