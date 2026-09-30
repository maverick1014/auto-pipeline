"""Failing tests: the city shows every session by its real session name.

Owner, 2026-09-30 (screenshot of the live city): two v4-plus sessions both
show as "session · v4-plus" in the rail and the message panel, impossible to
tell apart, while Orca shows their real names (plus-manager, consignment, ...).

Where the real name lives (checked on pc2, Claude Code 2.1.285): the session's
transcript (the hook payload's "transcript_path", a .jsonl file) gets these
lines, appended again and again, the newest last:

    {"type": "custom-title", "customTitle": "<name>", "sessionId": ...}
        set by `claude --name`, `/rename`, or the SessionStart hook
        bin/agent-name.sh (sessionTitle)
    {"type": "agent-name", "agentName": "<name>", "sessionId": ...}
        written next to custom-title, same name
    {"type": "ai-title", "aiTitle": "<title>", "sessionId": ...}
        the title Claude Code makes up from the talk

CONTRACT

  bin/agent-city-hook.sh: every line also has "tp", the payload's
    transcript_path as the JSON-escaped string value; "" when missing or
    longer than 1024 bytes. (tests/test_agent_city_hook.py KEYS has "tp".)
    The relay never sends it: to_wire (bin/agent_city_relay.py) keeps its own
    field list, "tp" is not in it.

  bin/agent_city.py:
    TitleReader(root=None, tail_bytes=2 MB)
      root: the only folder it reads under. Default: $CLAUDE_CONFIG_DIR/projects
      when that variable is set, else ~/.claude/projects.
      .title(path) -> the newest customTitle, else the newest agentName,
        else the newest aiTitle, else "". "" also when path is empty, not
        absolute, does not end in ".jsonl", is not inside root (after
        realpath: a symlink out of root does not count), is missing or
        unreadable. Never raises.
      Cheap: per path it keeps how far it has read and the titles found so
        far; a later call reads only the new bytes (only whole lines; a last
        line with no newline yet waits for the next call). A file that got
        shorter is read again from the start. The first read of a file reads
        at most its last tail_bytes (the titles are appended again and
        again, the newest is always near the end).
    CityState(..., titles=None): titles is the TitleReader to use (tests pass
      one with their own root); None -> TitleReader().
    For a session's own line (sid set, aid empty) whose session is a
      citizen (not the governor): the citizen's label becomes the title
      (cut to 40 characters) when the title is not "" and differs:
        - on the line that spawns it: the "spawn" event already carries the
          title as "label" (a title wins over a name world.json saved);
        - later: one {"type": "label", "id": <citizen id>, "label": <title>}
          event to every client, only when it changed.
      The Reducer's record changes too, so a new client's snapshot and
      world.json "names" (restart) have the new label. A subagent's line
      (aid set) never takes the session's title. Empty title -> the label
      stays what it was ("session", the role, or a saved name).

  bin/agent-city.html:
    apply({type: "label", id, label}) sets that citizen's label (the person
      tag, the rail row, the panel title and the chat lines all go through
      nameOf(c)); an unknown id does nothing.
    nameOf(c): as before ("<label> · <task>", never the same text twice),
      plus: when another citizen that is not gone and not remote has the
      same text, " #" and the last 4 characters of c.id are added, so two
      rows never read the same.

Run: python3 -m unittest tests.test_agent_city_session_names </dev/null
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, ac, run_sim  # noqa: E402

import agent_city_relay as relay  # noqa: E402  (bin/ is on sys.path via test_agent_city_people)

REPO = "/work/v4/v4-plus/.git"


def title_line(kind, value, sid="s1"):
    key = {"custom-title": "customTitle", "agent-name": "agentName", "ai-title": "aiTitle"}[kind]
    return json.dumps({"type": kind, key: value, "sessionId": sid}) + "\n"


def talk_line(text="hello", sid="s1"):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text},
                       "sessionId": sid}) + "\n"


class TitleCase(unittest.TestCase):

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_titles_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.root = os.path.join(self.base, "projects")
        os.makedirs(os.path.join(self.root, "-work-v4-plus"))

    def transcript(self, name="s1", lines=(), folder="-work-v4-plus"):
        path = os.path.join(self.root, folder, name + ".jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("".join(lines))
        return path

    def add(self, path, *lines):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("".join(lines))


class TestTitleReader(TitleCase):

    def reader(self, **kw):
        return ac.TitleReader(root=self.root, **kw)

    def test_custom_title_wins(self):
        p = self.transcript(lines=[title_line("ai-title", "Sales invoice overpayment"),
                                   title_line("custom-title", "plus-manager"),
                                   title_line("agent-name", "plus-manager"), talk_line()])
        self.assertEqual(self.reader().title(p), "plus-manager")

    def test_agent_name_when_no_custom_title(self):
        p = self.transcript(lines=[title_line("agent-name", "consignment"),
                                   title_line("ai-title", "Consignment phase 3")])
        self.assertEqual(self.reader().title(p), "consignment")

    def test_ai_title_last(self):
        p = self.transcript(lines=[talk_line(), title_line("ai-title", "Menu visibility")])
        self.assertEqual(self.reader().title(p), "Menu visibility")

    def test_nothing_found(self):
        self.assertEqual(self.reader().title(self.transcript(lines=[talk_line()])), "")

    def test_the_newest_one_counts(self):
        p = self.transcript(lines=[title_line("custom-title", "old name"), talk_line(),
                                   title_line("custom-title", "new name")])
        self.assertEqual(self.reader().title(p), "new name")

    def test_a_later_rename_is_seen(self):
        r = self.reader()
        p = self.transcript(lines=[title_line("ai-title", "First talk")])
        self.assertEqual(r.title(p), "First talk")
        self.add(p, talk_line(), title_line("custom-title", "plus-manager"))
        self.assertEqual(r.title(p), "plus-manager")
        self.add(p, title_line("custom-title", "plus-manager 2"))
        self.assertEqual(r.title(p), "plus-manager 2")

    def test_titles_found_earlier_are_kept(self):
        r = self.reader()
        p = self.transcript(lines=[title_line("custom-title", "plus-manager")])
        self.assertEqual(r.title(p), "plus-manager")
        self.add(p, *[talk_line("x" * 50) for _ in range(20)])
        self.assertEqual(r.title(p), "plus-manager")

    def test_a_half_written_line_waits(self):
        r = self.reader()
        p = self.transcript(lines=[title_line("ai-title", "First talk")])
        full = title_line("custom-title", "plus-manager")
        self.add(p, full[:25])
        self.assertEqual(r.title(p), "First talk")
        self.add(p, full[25:])
        self.assertEqual(r.title(p), "plus-manager")

    def test_a_shorter_file_is_read_again(self):
        r = self.reader()
        p = self.transcript(lines=[talk_line("y" * 200), title_line("custom-title", "old")])
        self.assertEqual(r.title(p), "old")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(title_line("ai-title", "fresh"))
        self.assertEqual(r.title(p), "fresh")

    def test_first_read_is_only_the_tail(self):
        p = self.transcript(lines=[title_line("custom-title", "early name")]
                            + [talk_line("z" * 100) for _ in range(100)]
                            + [title_line("ai-title", "late title")])
        self.assertEqual(self.reader(tail_bytes=4096).title(p), "late title")
        self.assertEqual(self.reader().title(p), "early name")

    def test_bad_lines_are_skipped(self):
        p = self.transcript(lines=['{"type": "custom-title", "customTitle": \n', "not json\n",
                                   title_line("ai-title", "ok title")])
        self.assertEqual(self.reader().title(p), "ok title")

    def test_only_inside_root(self):
        outside = os.path.join(self.base, "elsewhere.jsonl")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write(title_line("custom-title", "secret"))
        link = os.path.join(self.root, "-work-v4-plus", "link.jsonl")
        os.symlink(outside, link)
        r = self.reader()
        self.assertEqual(r.title(outside), "")
        self.assertEqual(r.title(link), "")
        self.assertEqual(r.title(os.path.join(self.root, "..", "elsewhere.jsonl")), "")

    def test_bad_paths_give_nothing(self):
        r = self.reader()
        txt = os.path.join(self.root, "-work-v4-plus", "notes.txt")
        with open(txt, "w", encoding="utf-8") as fh:
            fh.write(title_line("custom-title", "x"))
        for path in ("", "relative/s1.jsonl", txt,
                     os.path.join(self.root, "-work-v4-plus", "missing.jsonl"), None, 42):
            with self.subTest(path=path):
                self.assertEqual(r.title(path), "")

    def test_default_root(self):
        old = os.environ.get("CLAUDE_CONFIG_DIR")
        self.addCleanup(lambda: os.environ.__setitem__("CLAUDE_CONFIG_DIR", old) if old is not None
                        else os.environ.pop("CLAUDE_CONFIG_DIR", None))
        os.environ["CLAUDE_CONFIG_DIR"] = self.base
        p = self.transcript(lines=[title_line("custom-title", "from config dir")])
        self.assertEqual(ac.TitleReader().title(p), "from config dir")


class CityCase(TitleCase):

    def setUp(self):
        super().setUp()
        self.world = os.path.join(self.base, "world.json")
        self.now = 1000.0
        self.st = self.state()

    def state(self):
        st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                          plans=ac.load_plans(), count_fn=lambda i: 0,
                          balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                          titles=ac.TitleReader(root=self.root),
                          main_fn=lambda identity: (os.getpid(), "gov"))   # city-roles: "gov" is the main manager
        self.client = st.add_client()
        self.client.queue.get_nowait()
        return st

    def line(self, sid, ev="PostToolUse", tp="", role="", aid="", at="", tool="Read", st=None):
        self.now += 1.0
        (st or self.st).feed_line({
            "ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "v4-plus",
            "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": REPO, "ask": "",
            "wt": "", "file": "", "tp": tp}, self.now)

    def events(self):
        out = []
        while not self.client.queue.empty():
            raw = self.client.queue.get_nowait()
            if isinstance(raw, bytes) and b"data:" in raw:
                out.append(json.loads(raw.decode("utf-8").split("data:", 1)[1]))
        return out

    def of(self, etype, events):
        return [e for e in events if e.get("type") == etype]

    def citizen_session(self, sid, tp):
        """A governor first (the repo's first roleless session), then SID as a citizen."""
        self.line("gov")
        self.line(sid, tp=tp)


class TestCitySessionNames(CityCase):

    def test_spawn_carries_the_real_name(self):
        tp = self.transcript("s1", [title_line("custom-title", "plus-manager")])
        self.citizen_session("s1", tp)
        spawns = [e for e in self.of("spawn", self.events()) if e["id"] == "s:s1"]
        self.assertEqual(len(spawns), 1)
        self.assertEqual(spawns[0]["label"], "plus-manager")
        self.assertEqual(spawns[0]["task"], "v4-plus")

    def test_two_sessions_of_one_repo_differ(self):
        a = self.transcript("s1", [title_line("custom-title", "plus-manager")])
        b = self.transcript("s2", [title_line("ai-title", "Consignment phase 3 brief")])
        self.citizen_session("s1", a)
        self.line("s2", tp=b)
        labels = {e["id"]: e["label"] for e in self.of("spawn", self.events())}
        self.assertEqual(labels["s:s1"], "plus-manager")
        self.assertEqual(labels["s:s2"], "Consignment phase 3 brief")

    def test_no_title_keeps_the_old_label(self):
        tp = self.transcript("s1", [talk_line()])
        self.citizen_session("s1", tp)
        self.line("s3", tp="")
        labels = {e["id"]: e["label"] for e in self.of("spawn", self.events())}
        self.assertEqual(labels["s:s1"], "session")
        self.assertEqual(labels["s:s3"], "session")

    def test_a_task_manager_gets_its_name_too(self):
        tp = self.transcript("tm", [title_line("custom-title", "session-names Task Manager")])
        self.line("tm", tp=tp, role="task-manager")
        spawn = [e for e in self.of("spawn", self.events()) if e["id"] == "s:tm"][0]
        self.assertEqual(spawn["label"], "session-names Task Manager")
        self.assertEqual(spawn["role"], "task-manager")

    def test_a_later_title_sends_one_label_event(self):
        tp = self.transcript("s1", [talk_line()])
        self.citizen_session("s1", tp)
        self.events()
        self.add(tp, title_line("ai-title", "Sales invoice overpayment"))
        self.line("s1", tp=tp)
        self.line("s1", tp=tp)
        labels = self.of("label", self.events())
        self.assertEqual(len(labels), 1, labels)
        self.assertEqual((labels[0]["id"], labels[0]["label"]), ("s:s1", "Sales invoice overpayment"))

    def test_a_rename_sends_another(self):
        tp = self.transcript("s1", [title_line("ai-title", "First talk")])
        self.citizen_session("s1", tp)
        self.events()
        self.add(tp, title_line("custom-title", "plus-manager"))
        self.line("s1", tp=tp)
        self.assertEqual([e["label"] for e in self.of("label", self.events())], ["plus-manager"])

    def test_long_titles_are_cut_to_40(self):
        long_title = "Brief plus variant remove stock di and much more words here"
        tp = self.transcript("s1", [title_line("ai-title", long_title)])
        self.citizen_session("s1", tp)
        spawn = [e for e in self.of("spawn", self.events()) if e["id"] == "s:s1"][0]
        self.assertEqual(spawn["label"], long_title[:40])

    def test_snapshot_and_restart_keep_the_new_label(self):
        tp = self.transcript("s1", [talk_line()])
        self.citizen_session("s1", tp)
        self.add(tp, title_line("custom-title", "plus-manager"))
        self.line("s1", tp=tp)
        client = self.st.add_client()
        snap = json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])
        self.assertIn("plus-manager", [a["label"] for a in snap["agents"] if a["id"] == "s:s1"])
        with open(self.world, encoding="utf-8") as fh:
            names = json.load(fh).get("names", {})
        self.assertEqual(names.get("s:s1", {}).get("label"), "plus-manager")

    def test_a_subagent_never_takes_the_session_title(self):
        tp = self.transcript("s1", [title_line("custom-title", "plus-manager")])
        self.citizen_session("s1", tp)
        self.line("s1", tp=tp, aid="w1", at="worker")
        self.line("s1", tp=tp, aid="w1", at="worker")
        events = self.events()
        spawn_w1 = [e for e in self.of("spawn", events) if e["id"] == "w1"]
        self.assertEqual([e["label"] for e in spawn_w1], ["worker"])
        self.assertEqual([e for e in self.of("label", events) if e["id"] == "w1"], [])

    def test_the_governor_gets_no_label_event(self):
        tp = self.transcript("gov", [title_line("custom-title", "v4-plus Manager")])
        self.line("gov", tp=tp)
        self.line("gov", tp=tp)
        events = self.events()
        self.assertEqual(self.of("label", events), [])
        self.assertEqual([e for e in self.of("spawn", events) if e["id"] == "s:gov"], [])

    def test_a_path_outside_the_root_is_never_read(self):
        outside = os.path.join(self.base, "s9.jsonl")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write(title_line("custom-title", "secret"))
        self.citizen_session("s9", outside)
        spawn = [e for e in self.of("spawn", self.events()) if e["id"] == "s:s9"][0]
        self.assertEqual(spawn["label"], "session")


class TestRelayNeverSendsThePath(unittest.TestCase):

    def test_to_wire_drops_tp(self):
        wire = relay.to_wire({"ev": "PostToolUse", "sid": "s1", "tp": "/Users/u/.claude/projects/x/s1.jsonl"},
                             {"rid": "r", "br": "main", "who": "me", "dev": "pc2"})
        self.assertNotIn("tp", wire)
        self.assertFalse([k for k, v in wire.items() if ".jsonl" in v])


PAGE_DRIVER = r"""
citizens.length = 0;
const mk = (id, label, task, extra) => Object.assign({ id, label, task, gone: false }, extra || {});
citizens.push(mk('s:aaaa1111', 'session', 'v4-plus'), mk('s:bbbb2222', 'session', 'v4-plus'),
              mk('s:cccc3333', 'plus-manager', 'v4-plus'), mk('w9', 'worker', 'Slice A'),
              mk('r:x', 'session', 'v4-plus', { remote: { who: 'ann', device: 'pc9' } }));
const twins = [nameOf(citizens[0]), nameOf(citizens[1]), nameOf(citizens[2]), nameOf(citizens[3])];
apply({ type: 'label', id: 's:bbbb2222', label: 'consignment' });
const renamed = [nameOf(citizens[0]), nameOf(citizens[1]), citizens[1].label];
apply({ type: 'label', id: 'nobody', label: 'x' });
citizens.push(mk('s:dddd4444', 'plus-manager', 'v4-plus', { gone: true }));
const goneIgnored = nameOf(citizens[2]);
__out = { twins, renamed, goneIgnored };
"""


class TestPageShowsTheName(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = run_sim(PAGE_DRIVER, {}, REQUIRED + ("nameOf",))

    def test_same_names_get_a_short_tell_apart_tag(self):
        self.assertEqual(self.out["twins"], ["session · v4-plus #1111", "session · v4-plus #2222",
                                             "plus-manager · v4-plus", "worker · Slice A"])

    def test_a_label_event_renames_and_the_tag_goes(self):
        self.assertEqual(self.out["renamed"], ["session · v4-plus", "consignment · v4-plus",
                                               "consignment"])

    def test_gone_and_remote_people_do_not_count(self):
        self.assertEqual(self.out["goneIgnored"], "plus-manager · v4-plus")


if __name__ == "__main__":
    unittest.main()
