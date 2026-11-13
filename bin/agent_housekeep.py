#!/usr/bin/env python3
"""agent_housekeep.py - the logic of bin/agent-housekeep.sh (python3 stdlib only).

Run by the bash entry, never by hand:

    agent_housekeep.py --root <PROJECT_ROOT> --plugin <PLUGIN_ROOT>
                       --gitdir <git dir> --kind orca|plain|cloud [--apply]

One mechanical pass: gone worktree lines, duplicate and suspect ideas, merged
and stale todos, related repos (read only), then the cleanup sweep. The result
is one block, printed, and with --apply written into <root>/agent_state.txt.
An internal error is a note line, never a traceback.
"""

import argparse
import fnmatch
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent_cleanup  # noqa: E402
import agent_conf  # noqa: E402

TAIL = re.compile(r" \| \d{4}-\d\d-\d\d \d\d:\d\d \| by \S+$")
KEPT = re.compile(r" \| kept \d{4}-\d\d-\d\d\s*$")
NOTE_WORDS = re.compile(r"(?<![A-Za-z0-9_-])(?:TMs?|task managers?|bounce"
                        r"|worker|S\d+)(?![A-Za-z0-9_-])", re.I)
NOTE_PAREN = re.compile(r"\([^()]*\)")
NOTE_LAST = re.compile(r"\([^()]*\)[ .]*$")
NOTE_SENT = re.compile(r"(?:^|(?<=\. ))(?:From|Seen) .*?(?:\. |$)", re.S)
REPO_DIRS = ("bin", "tests", "skills", "agents", "hooks", "requirements",
             "mock")
DATE_TIME = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d")
EXTS = (".sh", ".py", ".md", ".txt", ".json", ".js", ".mjs", ".html", ".conf",
        ".default")
CLEAN_LINE = re.compile(r"^HOUSEKEEP \d{4}-\d\d-\d\d \d\d:\d\d: clean$")


def read_lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def atomic_write(path, text):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", errors="surrogateescape",
                  newline="") as fh:
            fh.write(text)
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except OSError:
            pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def whole_word(name, text):
    return re.search(r"(?<![A-Za-z0-9_-])" + re.escape(name)
                     + r"(?![A-Za-z0-9_-])", text, re.I) is not None


def idea_text(line):
    line = KEPT.sub("", line)
    m = TAIL.search(line)
    return (line[:m.start()] if m else line).strip()


def idea_day(line):
    m = TAIL.search(KEPT.sub("", line))
    return m.group(0)[3:13] if m else None


def cut_note(text):
    """The text without its provenance note (P1, P2, P3)."""
    text = NOTE_PAREN.sub(lambda m: " " if NOTE_WORDS.search(m.group(0))
                          else m.group(0), text)
    text = NOTE_LAST.sub(" ", text)
    return NOTE_SENT.sub(" ", text)


class Housekeep(object):
    def __init__(self, args):
        self.root = args.root
        self.plugin = args.plugin
        self.gitdir = args.gitdir
        self.kind = args.kind
        self.apply = args.apply
        self.now = os.environ.get("AGENT_FAKE_NOW") or time.strftime(
            "%Y-%m-%d %H:%M")
        self.epoch = int(time.mktime(time.strptime(self.now,
                                                   "%Y-%m-%d %H:%M")))
        self.sweep = agent_cleanup.Sweep(self.root, self.plugin, self.kind,
                                         False, True)
        self.verb = "removed" if self.apply else "would remove"
        self.removed = []
        self.flags_gone = []
        self.flags_pane = []
        self.flags_merged = []
        self.flags_stale = []
        self.suspects = []
        self.related = []
        self.notes = []
        self.cleanup = []
        self.wt_lines = []   # (literal path, module, status)

    # ---- small helpers

    def note(self, text):
        if text not in self.notes:
            self.notes.append(text)

    def path(self, name):
        return os.path.join(self.root, name)

    def file_cmd(self, *args):
        return agent_cleanup.run(
            [os.path.join(self.plugin, "bin", "agent-file.sh")] + list(args),
            cwd=self.root, timeout=self.sweep.t, env=self.sweep.env)

    def minutes_since(self, text):
        then = int(time.mktime(time.strptime(text, "%Y-%m-%d %H:%M")))
        return (self.epoch - then) // 60

    # ---- gather

    def gather(self):
        sw = self.sweep
        sw.gather_git()
        sw.base()
        sw.gather_orca()
        for text, quiet in sw.notes:
            if quiet:
                continue
            if text.startswith("orca not answering"):
                continue
            self.note(text)
        if self.kind == "orca" and not (sw.list_ok and sw.ps_ok):
            self.note("orca not answering: worktree lines not checked")

    # ---- a. worktree lines

    def read_worktree_file(self):
        out = []
        for line in read_lines(self.path("agent_worktree.txt")):
            if not line.strip():
                continue
            parts = line.split(" | ")
            path = parts[0].strip()
            if not path:
                continue
            module = parts[1] if len(parts) > 1 else ""
            status = parts[2].strip() if len(parts) > 2 else ""
            out.append((parts[0], module, status))
        self.wt_lines = out

    def worktree_lines(self):
        sw = self.sweep
        self.read_worktree_file()
        if not self.wt_lines:
            return
        orca = self.kind == "orca"
        if orca and not (sw.list_ok and sw.ps_ok):
            return
        if not sw.wts_ok:
            self.note("git worktree list failed: worktree lines not checked")
            return
        local = set(agent_cleanup.real(r["path"]) for r in sw.wts
                    if os.path.isdir(r["path"]))
        uncertain = orca and (bool(sw.unreachable) or not sw.env_list_ok)
        done = set()
        for literal, module, status in self.wt_lines:
            path = literal.strip()
            rp = agent_cleanup.real(path)
            norm = os.path.normpath(path)
            far = any(norm in m["paths"] for m in sw.machines)
            present = rp in local or far
            pane = bool(sw.ps.get(rp)) or any(
                m["ps"].get(norm) for m in sw.machines)
            human = "human-direct" in module
            keep_status = human or status in ("working", "final")
            if not present:
                if pane:
                    continue
                if keep_status:
                    if not uncertain:
                        says = "human-direct" if human else status
                        self.flags_gone.append(
                            "flag: worktree line %s: folder gone, line says %s"
                            % (path, says))
                    continue
                if uncertain or rp in done:
                    continue
                done.add(rp)
                if self.apply:
                    res = self.file_cmd("worktree", "rm", literal)
                    if not res.ok:
                        continue
                self.removed.append(
                    "%s: worktree line %s (folder gone, no live pane)"
                    % (self.verb, path))
            elif orca and status in ("working", "final") and not pane:
                self.flags_pane.append(
                    "flag: worktree line %s: %s, no live agent pane"
                    % (path, status))

    # ---- b. todo

    def interval(self):
        try:
            conf = agent_conf.load(self.path("agent.conf"))
            val = int(conf.get("housekeep_interval_min", "0"))
        except (OSError, ValueError):
            return 120
        return val if val > 0 else 120

    def todo_rows(self):
        rows = []
        for line in read_lines(self.path("agent_todo.txt")):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(" | ")]
            if parts[0]:
                rows.append(parts)
        return rows

    @staticmethod
    def field(parts, key):
        for p in parts[1:]:
            if p.startswith(key + " "):
                return p[len(key) + 1:].strip()
        return None

    def worktree_for(self, name, parts):
        """The agent_worktree.txt lines of this task: (path) list."""
        on = self.field(parts, "on")
        on_path = None
        if on:
            bits = on.split(None, 1)
            if len(bits) == 2:
                on_path = os.path.normpath(bits[1].strip())
        found = []
        for literal, module, _status in self.wt_lines:
            path = literal.strip()
            if (module.strip() == name
                    or os.path.basename(path.rstrip("/")) == name
                    or (on_path and os.path.normpath(path) == on_path)):
                found.append(path)
        return found

    def branch_of(self, path):
        sw = self.sweep
        rp = agent_cleanup.real(path)
        for r in sw.wts:
            if agent_cleanup.real(r["path"]) == rp and r.get("branch"):
                return r["branch"]
        norm = os.path.normpath(path)
        for m in sw.machines:
            for r in m["rows"]:
                if (os.path.normpath(r.get("path") or "") == norm
                        and r.get("branch")):
                    return agent_cleanup.strip_heads(r["branch"])
        return None

    def merged_flag(self, name, wt_paths):
        sw = self.sweep
        fp = sw.first_parent_set()
        cands = []
        for p in wt_paths:
            b = self.branch_of(p)
            if b and b not in cands:
                cands.append(b)
        for b in sorted(set(list(sw.local_refs) + list(sw.origin_refs))):
            if (b == name or b.endswith("/" + name)) and b not in cands:
                cands.append(b)
        if fp is not False:
            for b in cands:
                for refname, refs in (("refs/heads/", sw.local_refs),
                                      ("refs/remotes/origin/", sw.origin_refs)):
                    tip = refs.get(b)
                    if tip and (refname + b) in sw.merged and tip not in fp:
                        return ("flag: todo %s: merged into origin/main "
                                "(branch %s)" % (name, b))
        res = sw.git("log", "--first-parent", "--format=%h %s",
                     "refs/remotes/origin/main", long=True)
        if res.ok:
            for line in res.out.splitlines():
                sha, _, subject = line.partition(" ")
                if subject == "Merge " + name or subject.startswith(
                        "Merge " + name + " "):
                    return ("flag: todo %s: merged into origin/main "
                            "(commit %s %s)" % (name, sha, subject))
        return None

    def todos(self):
        rows = self.todo_rows()
        limit = self.interval()
        for parts in rows:
            name = parts[0]
            wt_paths = self.worktree_for(name, parts)
            if self.sweep.base_ok:
                flag = self.merged_flag(name, wt_paths)
                if flag:
                    self.flags_merged.append(flag)
            waiting = any(p.startswith("waiting") for p in parts[1:])
            if wt_paths or waiting:
                continue
            times = []
            opened = self.field(parts, "opened")
            if opened and DATE_TIME.fullmatch(opened):
                times.append(opened)
            stage = self.field(parts, "stage")
            if stage:
                m = re.search(r"since (\d{4}-\d\d-\d\d \d\d:\d\d)", stage)
                if m:
                    times.append(m.group(1))
            if not times:
                continue
            age = self.minutes_since(max(times))
            if age > limit:
                self.flags_stale.append(
                    "flag: todo %s: stale, no worktree line and no open "
                    "wait for %dm" % (name, age))

    # ---- c. ideas

    def ideas(self):
        path = self.path("agent_ideas.txt")
        lines = read_lines(path)
        first = {}
        dups = []   # (n, m, text)
        for i, line in enumerate(lines, 1):
            text = idea_text(line)
            if not text:
                continue
            if text in first:
                dups.append((i, first[text], text))
            else:
                first[text] = i
        removed_ns = set()
        for n, m, text in sorted(dups, reverse=True):
            if self.apply:
                cur = read_lines(path)
                if n > len(cur) or cur[n - 1] != lines[n - 1]:
                    continue
                if not self.file_cmd("idea", "rm", str(n)).ok:
                    continue
            removed_ns.add(n)
        for n, m, text in sorted(dups):
            if n in removed_ns or not self.apply:
                self.removed.append("%s: idea %d, a duplicate of idea %d: %s"
                                    % (self.verb, n, m, text[:80]))
        current = read_lines(path) if self.apply else lines
        done = []
        for line in read_lines(self.path("agent_completed.txt")):
            parts = [p.strip() for p in line.split(" | ")]
            if len(parts) < 2 or not re.fullmatch(r"\d{4}-\d\d-\d\d", parts[0]):
                continue
            dropped = any(p.startswith("dropped:") for p in parts[2:])
            done.append((parts[0], parts[1], dropped))
        for n, line in enumerate(current, 1):
            text = idea_text(line)
            if not text:
                continue
            if KEPT.search(line):
                continue
            reasons = []
            day = idea_day(line)
            if day:
                body = cut_note(text)
                for date, task, dropped in done:
                    if date > day and task and whole_word(task, body):
                        r = "names task %s, %s %s" % (
                            task, "dropped" if dropped else "done", date)
                        if r not in reasons:
                            reasons.append(r)
            for word in self.missing_files(text):
                reasons.append("names %s, no such file" % word)
            if reasons:
                self.suspects.append("suspect: idea %d: %s | %s"
                                     % (n, text[:80], "; ".join(reasons)))

    def tracked_names(self):
        if getattr(self, "_tracked", None) is None:
            res = self.sweep.git("ls-files")
            self._tracked = set(os.path.basename(l)
                                for l in res.out.splitlines()) if res.ok \
                else set()
        return self._tracked

    def missing_files(self, text):
        text = re.sub(r"\w+://\S+", " ", text)
        out = []
        for word in re.findall(r"[A-Za-z0-9_./~-]+", text):
            word = word.rstrip(".,:;)")
            if word.startswith("./"):
                word = word[2:]
            if not word.endswith(EXTS) or word in out:
                continue
            if "/" in word:
                if word.split("/")[0] not in REPO_DIRS or not os.path.isdir(
                        os.path.join(self.root, word.split("/")[0])):
                    continue
                found = os.path.exists(os.path.join(self.root, word))
            elif fnmatch.fnmatch(word, "agent_*.txt") or word.endswith(".md"):
                found = os.path.exists(os.path.join(self.root, word)) \
                    or word in self.tracked_names()
            else:
                continue
            if not found:
                out.append(word)
        return out

    # ---- d. related repos

    def related_repos(self):
        rows = self.todo_rows()
        wanted = []
        for parts in rows:
            for key in ("by", "cross"):
                x = self.field(parts, key)
                if x:
                    wanted.append((parts[0], key, x.split()[0] if x.split()
                                   else x))
        if not wanted:
            return
        res = self.file_cmd("repos")
        known = {}
        if res.ok:
            for line in res.out.splitlines():
                line = line.strip()
                if line:
                    known.setdefault(os.path.basename(line.rstrip("/")), line)
        me = agent_cleanup.real(self.root)
        seen = set()
        for name, key, x in wanted:
            if (name, x) in seen:
                continue
            repo = known.get(x)
            if repo is None:
                if key == "cross":
                    seen.add((name, x))
                    text = "related: %s: not found on this machine, skipped" % x
                    if text not in self.related:
                        self.related.append(text)
                continue
            if agent_cleanup.real(repo) == me:
                continue
            seen.add((name, x))
            self.check_repo(name, x, repo)

    def check_repo(self, name, x, repo):
        head = "related: %s (%s): task %s" % (x, repo, name)
        for line in read_lines(os.path.join(repo, "agent_todo.txt")):
            if line.split(" | ")[0].strip() == name:
                for wl in read_lines(os.path.join(repo, "agent_worktree.txt")):
                    parts = wl.split(" | ")
                    if len(parts) < 2:
                        continue
                    if (parts[1].strip() == name
                            or os.path.basename(parts[0].strip().rstrip("/"))
                            == name):
                        return
                self.related.append(head + " open there, no worktree line there")
                return
        hit = None
        for line in read_lines(os.path.join(repo, "agent_completed.txt")):
            parts = [p.strip() for p in line.split(" | ")]
            if len(parts) >= 2 and parts[1] == name and re.fullmatch(
                    r"\d{4}-\d\d-\d\d", parts[0]):
                dropped = any(p.startswith("dropped:") for p in parts[2:])
                hit = (parts[0], dropped)
        if hit:
            self.related.append("%s not open there (%s %s)" % (
                head, "dropped" if hit[1] else "done", hit[0]))
        else:
            self.related.append(head + " not open there")

    # ---- e. cleanup

    def run_cleanup(self):
        argv = [os.path.join(self.plugin, "bin", "agent-cleanup.sh")]
        if self.apply:
            argv.append("--apply")
        argv.append("--short")
        res = agent_cleanup.run(argv, cwd=self.root, timeout=600,
                                env=dict(os.environ))
        for line in res.out.splitlines():
            if line.startswith("CLEANUP: "):
                self.cleanup.append("cleanup: " + line[len("CLEANUP: "):])

    # ---- the block

    def stage(self, fn):
        try:
            fn()
        except Exception as exc:
            self.note("internal error (%s)" % type(exc).__name__)

    def body(self):
        return (self.removed + self.flags_gone + self.flags_pane
                + self.flags_merged + self.flags_stale + self.suspects
                + self.related + ["note: " + n for n in self.notes]
                + self.cleanup)

    def block(self):
        body = self.body()
        if not body:
            return ["HOUSEKEEP %s: clean" % self.now]
        return ["=== HOUSEKEEP %s ===" % self.now] + ["  " + l for l in body]

    def write_state(self, block):
        path = self.path("agent_state.txt")
        try:
            with open(path, encoding="utf-8", errors="surrogateescape",
                      newline="") as fh:
                old = fh.read().splitlines(True)
        except OSError:
            old = []
        new = "".join(l + "\n" for l in block)
        out = []
        placed = False
        i = 0
        while i < len(old):
            bare = old[i].rstrip("\r\n")
            if bare.startswith("=== HOUSEKEEP ") and bare.endswith(" ==="):
                i += 1
                while i < len(old) and old[i].startswith("  "):
                    i += 1
                if not placed:
                    out.append(new)
                    placed = True
                continue
            if CLEAN_LINE.match(bare):
                if not placed:
                    out.append(new)
                    placed = True
                i += 1
                continue
            out.append(old[i])
            i += 1
        if not placed:
            if out and not out[-1].endswith("\n"):
                out[-1] += "\n"
            out.append(new)
        atomic_write(path, "".join(out))

    def go(self):
        if self.apply:
            try:
                os.makedirs(self.gitdir, exist_ok=True)
                atomic_write(os.path.join(self.gitdir, "agent_housekeep.last"),
                             "%d %s\n" % (self.epoch, self.now))
            except OSError:
                self.note("stamp not written")
        self.stage(self.gather)
        self.stage(self.worktree_lines)
        self.stage(self.todos)
        self.stage(self.ideas)
        self.stage(self.related_repos)
        self.stage(self.run_cleanup)
        block = self.block()
        sys.stdout.write("".join(l + "\n" for l in block))
        sys.stdout.flush()
        if self.apply:
            try:
                self.write_state(block)
            except Exception as exc:
                sys.stdout.write("  note: internal error (%s)\n"
                                 % type(exc).__name__)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--gitdir", required=True)
    ap.add_argument("--kind", default="plain")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    try:
        Housekeep(args).go()
    except Exception as exc:
        print("HOUSEKEEP: note: internal error (%s)" % type(exc).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
