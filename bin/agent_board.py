#!/usr/bin/env python3
"""agent_board.py - the table behind `agent-file.sh board` ("show todo"). Python 3.9, standard library only.

    agent_board.py --root <main repo> --state-dir <git toplevel of the cwd> --cwd <cwd>
                   --now "YYYY-MM-DD HH:MM" --lang <zh|en> --host <machine> [--self]

Read only: it writes nothing. One file, no imports of sibling modules, so no __pycache__ is written.
Prints one GitHub markdown table (or one line "无" / "none"), then note lines.

Rows (whole repo): every line of agent_todo.txt; every human-direct line of agent_worktree.txt ("<repo> Helper");
the state lines (OWNER TODO, PARKED, WORKER) of the main repo's agent_state.txt and of every agent_worktree.txt
folder that is on this machine (a folder that is not here: a note line after the table).
Rows (--self): the session's own task (its todo line, else its "TODO LINE:" in its own agent_state.txt, else the
human-direct line of its folder, else one bare row) plus the state lines of its own agent_state.txt only.
"""

import argparse
import datetime
import os
import re
import sys

DATE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
FMT = "%Y-%m-%d %H:%M"
HELPER_ROLE = "task manager, human-direct"

HEAD = {
    "zh": ["任务", "内容", "状态", "位置", "估时", "已工作", "已等待", "预计完成"],
    "en": ["Task", "What", "Status", "Where", "Est", "Work", "Wait", "Done by"],
}
STATUS = {
    "zh": {"mock": "等你：看样稿", "question": "等你：回答问题", "review": "等你：验收",
           "running": "进行中", "hold": "暂缓", "queue": "排队中", "owner": "你的待办",
           "parked": "搁置的问题"},
    "en": {"mock": "waits on you: mock check", "question": "waits on you: question",
           "review": "waits on you: review", "running": "running", "hold": "held",
           "queue": "queued", "owner": "your to-do", "parked": "parked question"},
}
# sort groups: waiting on the owner, running, held or queued, OWNER TODO, parked
G_OWNER_WAIT, G_RUNNING, G_HELD, G_OWNER_TODO, G_PARKED = 0, 1, 2, 3, 4
KIND_GROUP = {"mock": G_OWNER_WAIT, "question": G_OWNER_WAIT, "review": G_OWNER_WAIT,
              "hold": G_HELD, "queue": G_HELD}
WHAT_MAX = 60
QUOTES = "\"'`“”‘’«»「」『』"


# ---------------------------------------------------------------- small helpers


def parse_time(text):
    try:
        return datetime.datetime.strptime(text.strip(), FMT)
    except (ValueError, AttributeError):
        return None


def minutes(a, b):
    """Whole minutes from a to b (b - a), never below 0; None when either is unknown."""
    if a is None or b is None:
        return None
    return max(0, int((b - a).total_seconds() // 60))


def fmt_min(n):
    if n is None:
        return "-"
    if n >= 1440:
        d, h = divmod(n // 60, 24)
        return "%dd %dh" % (d, h) if h else "%dd" % d
    if n >= 60:
        h, m = divmod(n, 60)
        return "%dh %dm" % (h, m) if m else "%dh" % h
    return "%dm" % n


def collapse(text):
    return " ".join(str(text).split())


def cut_what(text):
    s = collapse(text)
    if len(s) <= WHAT_MAX:
        return s
    limit = WHAT_MAX - 1
    kept = s[:limit]
    if s[limit] != " ":
        i = kept.rfind(" ")
        if i > 0:
            kept = kept[:i]
    return kept.rstrip() + "…"


def cell(text):
    return collapse(text).replace("|", "\\|") or "-"


def short_path(path, home):
    if home and home != "/" and (path == home or path.startswith(home.rstrip("/") + "/")):
        return "~" + path[len(home.rstrip("/")):]
    return path


def read_lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


# ---------------------------------------------------------------- the board


class Board:
    def __init__(self, args):
        self.root = os.path.normpath(args.root)
        self.state_dir = os.path.normpath(args.state_dir)
        self.cwd = args.cwd
        self.now = parse_time(args.now) or datetime.datetime.now().replace(second=0, microsecond=0)
        self.lang = "zh" if args.lang == "zh" else "en"
        self.host = args.host
        self.self_mode = args.self_mode
        self.home = os.path.expanduser("~")
        self.words = STATUS[self.lang]
        self.rows = []
        self.notes = []
        self.seq = 0

    # -- words

    def word(self, key):
        return self.words[key]

    def where_here(self, path):
        return "%s, %s" % (self.host, short_path(path, self.home))

    def where_path(self, path):
        """This machine and the path when the folder is here, else the path alone."""
        if os.path.isdir(path):
            return self.where_here(path)
        return short_path(path, self.home)

    def done_by(self, est, work):
        if est is None or work is None:
            return "-"
        if work >= est:
            return "超出估时" if self.lang == "zh" else "over est"
        when = self.now + datetime.timedelta(minutes=est - work)
        clock = when.strftime("%H:%M")
        day = when.date()
        today = self.now.date()
        if day == today:
            return clock
        if day == today + datetime.timedelta(days=1):
            return ("明天 " + clock) if self.lang == "zh" else (clock + " tomorrow")
        stamp = when.strftime("%Y-%m-%d")
        return ("%s %s" % (stamp, clock)) if self.lang == "zh" else ("%s on %s" % (clock, stamp))

    # -- rows

    def add(self, group, when, task, what, status, where, est="-", work="-", wait="-", done="-"):
        """when: "YYYY-MM-DD HH:MM" or None (no date sorts last, file order)."""
        self.seq += 1
        key = (group, 0 if when else 1, when or "", self.seq)
        cells = [cell(task), cell(cut_what(what)), cell(status), cell(where), cell(est),
                 cell(work), cell(wait), cell(done)]
        self.rows.append((key, cells))

    # -- the todo lines

    def parse_todo(self, line):
        f = line.split(" | ")
        t = {"name": f[0].strip(), "what": f[2] if len(f) > 2 else "", "est": None,
             "opened": None, "wkind": None, "wsince": None, "wnote": "", "waited": 0,
             "machine": None, "path": None}
        for x in f[3:]:
            m = re.match(r"est (\d+)m$", x)
            if m and t["est"] is None:
                t["est"] = int(m.group(1))
                continue
            m = re.match(r"opened (%s)" % DATE, x)
            if m and t["opened"] is None:
                t["opened"] = m.group(1)
                continue
            m = re.match(r"waiting (\S+) since (%s)(?:: (.*))?$" % DATE, x)
            if m and t["wkind"] is None:
                t["wkind"], t["wsince"], t["wnote"] = m.group(1), m.group(2), m.group(3) or ""
                continue
            m = re.match(r"waited (\d+)m$", x)
            if m:
                t["waited"] = int(m.group(1))
                continue
            m = re.match(r"on (\S+)(?: (.*))?$", x)
            if m and t["machine"] is None:
                t["machine"], t["path"] = m.group(1), (m.group(2) or "").strip()
        return t

    def worktree_where(self, task, wt_lines):
        for f in wt_lines:
            if len(f) >= 2 and f[1] != HELPER_ROLE and (f[1] == task or os.path.basename(f[0].rstrip("/")) == task):
                return self.where_path(f[0])
        return None

    def todo_row(self, t, wt_lines, own_dir=None):
        opened = parse_time(t["opened"]) if t["opened"] else None
        wsince = parse_time(t["wsince"]) if t["wsince"] else None
        wait = t["waited"]
        if wsince is not None:
            wait += minutes(wsince, self.now)
        clock = minutes(opened, self.now)
        work = None if clock is None else max(0, clock - wait)
        kind = t["wkind"] if t["wkind"] in KIND_GROUP else None
        status = self.word(kind or "running")
        if kind and t["wnote"]:
            status += " · " + t["wnote"]
        group = KIND_GROUP.get(kind, G_RUNNING)
        if kind:
            when = t["wsince"]
        else:
            when = t["opened"]
        if t["machine"]:
            where = t["machine"] + (", " + short_path(t["path"], self.home) if t["path"] else "")
        else:
            where = self.worktree_where(t["name"], wt_lines)
            if where is None:
                where = self.where_here(own_dir) if own_dir else "-"
        self.add(group, when, t["name"], t["what"] or "-", status, where,
                 est=fmt_min(t["est"]), work=fmt_min(work), wait=fmt_min(wait),
                 done=self.done_by(t["est"], work))

    def helper_row(self, f):
        what = "-"
        if len(f) > 2 and f[2].startswith("task:"):
            what = f[2][5:].strip() or "-"
        since = None
        if len(f) > 3:
            m = re.match(r"since (%s)" % DATE, f[3])
            since = m.group(1) if m else None
        task = "%s Helper" % os.path.basename(self.root)
        self.add(G_RUNNING, since, task, what, self.word("running"), self.where_path(f[0]))

    # -- the state lines

    def state_rows(self, folder):
        """OWNER TODO, PARKED and WORKER lines of <folder>/agent_state.txt."""
        name = os.path.basename(folder.rstrip("/")) or folder
        where = self.where_here(folder)
        for line in read_lines(os.path.join(folder, "agent_state.txt")):
            m = re.match(r"PARKED: (.*)$", line)
            if m:
                parts = m.group(1).split(" | ")
                since = None
                for x in parts[1:]:
                    mm = re.match(r"since (%s)" % DATE, x)
                    if mm:
                        since = mm.group(1)
                task = parts[1].strip() if len(parts) > 1 and not parts[1].startswith("since ") else name
                wait = fmt_min(minutes(parse_time(since), self.now)) if since else "-"
                self.add(G_PARKED, since, task or name, parts[0], self.word("parked"), where, wait=wait)
                continue
            m = re.match(r"WORKER (\d+): (.*)$", line)
            if m:
                parts = m.group(2).split(" | ")
                since = None
                for x in parts[1:]:
                    mm = re.match(r"since (%s)" % DATE, x)
                    if mm:
                        since = mm.group(1)
                label = ("%s 工人 %s" if self.lang == "zh" else "%s worker %s") % (name, int(m.group(1)))
                work = fmt_min(minutes(parse_time(since), self.now)) if since else "-"
                self.add(G_RUNNING, since, label, parts[0], self.word("running"), where, work=work)
                continue
            item = self.owner_item(line)
            if item:
                text, stamp = item
                wait = fmt_min(minutes(parse_time(stamp), self.now)) if stamp else "-"
                self.add(G_OWNER_TODO, stamp, "-", text, self.word("owner"), "-", wait=wait)

    @staticmethod
    def owner_item(line):
        """(item text, stamp or None) when the line holds the marker "OWNER TODO:", else None.

        Capitals and the colon, anywhere in the line, not right after a quote mark. Without the colon it is a
        mention. The item text is what follows the colon. A "YYYY-MM-DD[ HH:MM]" stamp at the start of the line
        (after spaces or a "-" / "*" bullet) is its date.
        """
        m = re.search(r"(?<![%s])OWNER TODO:(.*)$" % re.escape(QUOTES), line)
        if not m or not m.group(1).strip():
            return None
        stamp = None
        d = re.match(r"\s*(?:[-*]\s+)?(\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?\s", line)
        if d:
            stamp = "%s %s" % (d.group(1), d.group(2) or "00:00")
        return m.group(1).strip(), stamp

    def own_todo_line(self):
        found = None
        for line in read_lines(os.path.join(self.state_dir, "agent_state.txt")):
            m = re.match(r"\s*TODO LINE: (.*)$", line)
            if m:
                found = m.group(1)
        return found

    # -- the two views

    def whole_repo(self):
        wt_lines = [l.split(" | ") for l in read_lines(os.path.join(self.root, "agent_worktree.txt")) if l.strip()]
        for line in read_lines(os.path.join(self.root, "agent_todo.txt")):
            if not line.strip():
                continue
            t = self.parse_todo(line)
            if t["name"]:
                self.todo_row(t, wt_lines)
        for f in wt_lines:
            if len(f) >= 2 and f[1] == HELPER_ROLE:
                self.helper_row(f)
        seen = set()
        for folder in [self.root] + [f[0] for f in wt_lines if f and f[0]]:
            norm = os.path.normpath(folder)
            if not os.path.isdir(norm):
                if norm not in seen:
                    self.notes.append(("不在本机，未读：%s" if self.lang == "zh" else
                                       "not on this machine, not read: %s") % folder)
                seen.add(norm)
                continue
            real = os.path.realpath(norm)
            if real in seen:
                continue
            seen.add(real)
            self.state_rows(norm)

    def own_view(self):
        folder = self.state_dir
        name = os.path.basename(folder.rstrip("/")) or folder
        in_root = os.path.realpath(folder) == os.path.realpath(self.root)
        wt_lines = [l.split(" | ") for l in read_lines(os.path.join(self.root, "agent_worktree.txt")) if l.strip()]
        found = False
        for line in read_lines(os.path.join(self.root, "agent_todo.txt")):
            if not line.strip():
                continue
            t = self.parse_todo(line)
            if t["name"] == name:
                self.todo_row(t, wt_lines, own_dir=folder)
                found = True
                break
        if not found and not in_root:
            line = self.own_todo_line()
            if line:
                t = self.parse_todo(line)
                if t["name"]:
                    self.todo_row(t, wt_lines, own_dir=folder)
                    found = True
        if not found:
            here = {os.path.realpath(folder), os.path.realpath(self.cwd)}
            for f in wt_lines:
                if len(f) >= 2 and f[1] == HELPER_ROLE and os.path.realpath(f[0]) in here:
                    self.helper_row(f)
                    found = True
                    break
        if not found:
            self.add(G_RUNNING, None, name, "-", self.word("running"), self.where_here(folder))
        if not in_root:
            self.state_rows(folder)

    # -- print

    def render(self):
        if not self.rows:
            out = ["无" if self.lang == "zh" else "none"]
            out += self.notes
            return "\n".join(out) + "\n"
        out = ["| " + " | ".join(HEAD[self.lang]) + " |", "|" + "---|" * len(HEAD[self.lang])]
        for _, cells in sorted(self.rows, key=lambda r: r[0]):
            out.append("| " + " | ".join(cells) + " |")
        if self.notes:
            out.append("")
            out += self.notes
        return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser(prog="agent_board.py")
    p.add_argument("--root", required=True)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--cwd", required=True)
    p.add_argument("--now", required=True)
    p.add_argument("--lang", default="en")
    p.add_argument("--host", default="-")
    p.add_argument("--self", dest="self_mode", action="store_true")
    args = p.parse_args()
    board = Board(args)
    if args.self_mode:
        board.own_view()
    else:
        board.whole_repo()
    sys.stdout.write(board.render())


if __name__ == "__main__":
    main()
