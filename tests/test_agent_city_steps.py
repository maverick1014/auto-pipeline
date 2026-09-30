"""Failing tests: city-work-anim bounce 1 -- no tool names over heads; say what it is doing in plain words
(owner, 2026-09-30: "for each action, no need to show the action on the head like bash, edit, update;
these are useless info. The really useful thing is to show what the agent is doing right now.";
main manager: the history's "Read x2 · Write x6 · Bash x2" line is the same useless info; the demo's
other-member worker stood still).

CONTRACT

  Server (bin/agent_city.py, Reducer -- the page lacked the data: a tool event only carried the kind):
    A "tool" event keeps "tool" (the kind: Edit, Write, Bash, Read, Other) and adds
      "name": the hook's own tool name (tool_name) when it is made of letters, digits and "_" only
              and at most 64 characters long, else "".
      "file": for Edit, Write, MultiEdit and NotebookEdit only, when the line's "file" (the hook's
              repo-relative path) is safe (_is_safe_rel_path): its last path part, at most 60
              characters. The key is left out otherwise. Never a folder, never a full path.
      "desc": for Agent and Task only, when the line has a "desc": at most 60 characters. Left out
              otherwise.
    A joined member's line (RemoteCity) never gives a "file", even if one came over the relay: other
    members' file names never show (requirements/city.md, Joining).

  Page, simulation section (runs in node, see test_agent_city_people):
    stepText(ev) -> what one tool event is doing, in plain words (i18n, zh and en):
        Edit / MultiEdit / NotebookEdit with a file -> step.edit    改 {file}      Editing {file}
        Write with a file                           -> step.write   写 {file}      Writing {file}
        Edit-like without a file                    -> step.editAny 改代码         Editing code
        Write without a file                        -> step.writeAny 写代码        Writing code
        Read                                        -> step.read    看文件         Reading files
        Grep / Glob / LS                            -> step.search  找代码         Searching code
        WebFetch / WebSearch                        -> step.web     查资料         Looking things up
        Bash                                        -> step.bash    跑命令         Running a command
        Agent / Task with a desc                    -> step.send    派出：{desc}   Sending out: {desc}
        Agent / Task without one                    -> step.sendAny 派出帮手       Sending a helper
        TodoWrite                                   -> step.plan    排计划         Planning
        SendMessage                                 -> step.message 发消息         Sending a message
        anything else                               -> step.other   忙着           Busy
      With no "name" (an older server, a remote line from an older member): from the kind -- Edit ->
      改代码, Write -> 写代码, Read -> 看文件, Bash -> 跑命令, Other -> 忙着.
      Only the file's last path part is ever shown; a file name longer than 24 characters is cut to 23
      plus "…", a desc longer than 20 to 19 plus "…".
    Every tool event (live, and a joined member's relayed one) sets c.step = stepText(ev).
    doingText(c) -> the one line over the head: '' unless workAction(c) is not '' (so nothing in the
      short pause, nothing while walking); else "<task> · <step>", where task is c.task cut to 13
      characters plus "…" when longer than 14; just "<step>" when c.task is empty or equal to c.label.
    No tool name ever floats over a head (no floater on a tool event; test_agent_city_polish).
    actTool(c, step) (the history line): plain-words steps, never tool names or counts -- see U10 in
      test_agent_city_ux_page.
    Demo (#demo): demoRemoteTick(dt) (in the simulation section) gives every demo member person (c.remote) that is not stuck, not
      done and in 'working' or 'building' one relayed tool line about every DEMO_REMOTE_TOOL_SEC = 1.6 s,
      through apply({ type: 'remote', who, device, dev, rid, br, ev: { type: 'tool', id, tool, name } })
      with names cycling Read, Edit, Bash, Grep (no file: other members never send one); nothing while
      a team relay is off (a `relays` entry with state 'off' -- the test anyRelayOff() makes; move
      anyRelayOff into the simulation section, or test `relays` there directly). update(dt) calls it
      when DEMO.

  3D view:
    updatePerson(c) pins a small ".doing" line over the head with doingText(c) (not while a bubble or
    a "?" is up there); the CSS has a .doing rule.

Run: python3 -m unittest tests.test_agent_city_steps </dev/null
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, ac, function_source, page, plan_views, run_sim  # noqa: E402
from test_agent_city_reducer import Case, R  # noqa: E402
from test_agent_city_idea_server import RemoteCase  # noqa: E402
from test_agent_city_ux_page import text_keys  # noqa: E402


def RF(ev, file=None, **kw):
    raw = R(ev, **kw)
    if file is not None:
        raw["file"] = file
    return raw


class TestToolEventNamesTheStep(Case):
    """Server: a tool event carries the raw tool name, the edited file's name, a Task's description."""

    def tool_event(self, **kw):
        out = self.feed(RF("PostToolUse", aid="a1", at="worker", **kw))
        tools = [e for e in out if e.get("type") == "tool"]
        self.assertEqual(len(tools), 1, out)
        return tools[0]

    def test_raw_name_rides_along(self):
        self.spawn()
        for tool, kind in {"Edit": "Edit", "MultiEdit": "Edit", "Grep": "Read", "WebSearch": "Read",
                           "TodoWrite": "Other", "Agent": "Other", "mcp__github__create_pull_request": "Other"}.items():
            with self.subTest(tool=tool):
                e = self.tool_event(tool=tool)
                self.assertEqual(e["tool"], kind)
                self.assertEqual(e["name"], tool)

    def test_odd_names_are_dropped(self):
        self.spawn()
        for tool in ("Bad Name!", "x" * 65, "Edit;rm"):
            with self.subTest(tool=tool):
                self.assertEqual(self.tool_event(tool=tool)["name"], "")

    def test_edited_file_gives_only_its_name(self):
        self.spawn()
        for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool):
                self.assertEqual(self.tool_event(tool=tool, file="src/pay/checkout.py")["file"], "checkout.py")
        self.assertEqual(self.tool_event(tool="Edit", file="README.md")["file"], "README.md")
        long = "f" * 70 + ".py"
        self.assertEqual(self.tool_event(tool="Edit", file="a/" + long)["file"], long[:60])

    def test_no_file_when_unsafe_or_not_an_edit(self):
        self.spawn()
        for tool, file in (("Edit", "../x.py"), ("Edit", "/abs/x.py"), ("Edit", ""), ("Bash", "x.py"), ("Read", "x.py")):
            with self.subTest(tool=tool, file=file):
                self.assertNotIn("file", self.tool_event(tool=tool, file=file))

    def test_task_description_for_agent_and_task_only(self):
        self.spawn()
        self.assertEqual(self.tool_event(tool="Agent", desc="设置页表单")["desc"], "设置页表单")
        self.assertEqual(self.tool_event(tool="Task", desc="d" * 80)["desc"], "d" * 60)
        self.assertNotIn("desc", self.tool_event(tool="Bash", desc="run the tests"))
        self.assertNotIn("desc", self.tool_event(tool="Agent"))

    def test_a_session_citizen_gets_the_same(self):
        out = self.feed(RF("PostToolUse", sid="w9", role="worker", tool="Write", file="docs/guide.md"))
        tool = [e for e in out if e.get("type") == "tool"][0]
        self.assertEqual((tool["tool"], tool["name"], tool["file"]), ("Write", "Write", "guide.md"))


class TestOtherMembersNeverShowAFile(RemoteCase):
    def test_remote_tool_event_has_a_name_but_no_file(self):
        self.send(ev="SessionStart", sid="w1", role="worker")
        events = self.send(ev="PostToolUse", sid="w1", role="worker", tool="Edit", file="src/secret/plan.py")
        tools = self.inner(events, "tool")
        self.assertEqual(len(tools), 1, events)
        self.assertEqual(tools[0]["name"], "Edit")
        self.assertNotIn("file", tools[0], "another member's file name never shows")


STEP_KEYS = {
    "step.edit": ("改 {file}", "Editing {file}"), "step.write": ("写 {file}", "Writing {file}"),
    "step.editAny": ("改代码", "Editing code"), "step.writeAny": ("写代码", "Writing code"),
    "step.read": ("看文件", "Reading files"), "step.search": ("找代码", "Searching code"),
    "step.web": ("查资料", "Looking things up"), "step.bash": ("跑命令", "Running a command"),
    "step.send": ("派出：{desc}", "Sending out: {desc}"), "step.sendAny": ("派出帮手", "Sending a helper"),
    "step.plan": ("排计划", "Planning"), "step.message": ("发消息", "Sending a message"),
    "step.other": ("忙着", "Busy"),
}

LONG_FILE = "a_really_long_file_name_for_tests.py"
LONG_DESC = "一二三四五六七八九十一二三四五六七八九十一二"
LONG_TASK = "一个非常长的任务名字超过十四个字"

STEP_CASES = [
    ({"tool": "Edit", "name": "Edit", "file": "checkout.py"}, "改 checkout.py"),
    ({"tool": "Edit", "name": "MultiEdit", "file": "a.py"}, "改 a.py"),
    ({"tool": "Edit", "name": "NotebookEdit", "file": "nb.ipynb"}, "改 nb.ipynb"),
    ({"tool": "Write", "name": "Write", "file": "README.md"}, "写 README.md"),
    ({"tool": "Edit", "name": "Edit", "file": "src/pay/checkout.py"}, "改 checkout.py"),
    ({"tool": "Edit", "name": "Edit", "file": LONG_FILE}, "改 " + LONG_FILE[:23] + "…"),
    ({"tool": "Edit", "name": "Edit"}, "改代码"),
    ({"tool": "Write", "name": "Write"}, "写代码"),
    ({"tool": "Read", "name": "Read"}, "看文件"),
    ({"tool": "Read", "name": "Grep"}, "找代码"),
    ({"tool": "Read", "name": "Glob"}, "找代码"),
    ({"tool": "Read", "name": "LS"}, "找代码"),
    ({"tool": "Read", "name": "WebFetch"}, "查资料"),
    ({"tool": "Read", "name": "WebSearch"}, "查资料"),
    ({"tool": "Bash", "name": "Bash"}, "跑命令"),
    ({"tool": "Other", "name": "Agent", "desc": "设置页表单"}, "派出：设置页表单"),
    ({"tool": "Other", "name": "Task", "desc": LONG_DESC}, "派出：" + LONG_DESC[:19] + "…"),
    ({"tool": "Other", "name": "Agent"}, "派出帮手"),
    ({"tool": "Other", "name": "TodoWrite"}, "排计划"),
    ({"tool": "Other", "name": "SendMessage"}, "发消息"),
    ({"tool": "Other", "name": "mcp__github__create_pull_request"}, "忙着"),
    ({"tool": "Edit"}, "改代码"),
    ({"tool": "Write"}, "写代码"),
    ({"tool": "Read"}, "看文件"),
    ({"tool": "Bash"}, "跑命令"),
    ({"tool": "Other"}, "忙着"),
]

STEPS_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
function buildLand(view){ landState(view); }
function tick(sec){ for (let i = 0; i < Math.round(sec * 10); i++) update(.1); }
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }],
  governors: 1, asks: [], shows: [], agents: [] });
const out = {};
out.steps = __payload.cases.map(ev => stepText(Object.assign({ type: 'tool', id: 'x' }, ev)));
out.en = Object.fromEntries(__payload.keys.map(k => [k, (TEXT.en || {})[k]]));
out.zh = Object.fromEntries(__payload.keys.map(k => [k, (TEXT.zh || {})[k]]));

// a live worker: the head line while it acts, nothing in the pause
apply({ type: 'spawn', id: 'w1', role: 'worker', label: 'worker', task: '写结账测试', terr: tid });
tick(20);
const w1 = byId('w1');
out.before = doingText(w1);
apply({ type: 'tool', id: 'w1', tool: 'Edit', name: 'Edit', file: 'checkout.py' });
out.step = w1.step;
out.doing = doingText(w1);
tick(7);
out.paused = doingText(w1);
apply({ type: 'tool', id: 'w1', tool: 'Bash', name: 'Bash' });
out.doingBash = doingText(w1);

// a long task is cut; a task that is just the label is left out
apply({ type: 'spawn', id: 'w2', role: 'worker', label: 'worker', task: __payload.longTask, terr: tid });
apply({ type: 'spawn', id: 'w3', role: 'worker', label: 'worker', task: 'worker', terr: tid });
tick(20);
apply({ type: 'tool', id: 'w2', tool: 'Read', name: 'Read' });
apply({ type: 'tool', id: 'w3', tool: 'Read', name: 'Grep' });
out.longTask = doingText(byId('w2'));
out.labelTask = doingText(byId('w3'));

// the history line: plain-words steps, the last 3 distinct, never a tool name or a count
const h = byId('w3');
h.acts = [];
for (const ev of [{ tool: 'Edit', name: 'Edit', file: 'a.py' }, { tool: 'Edit', name: 'Edit', file: 'a.py' },
                  { tool: 'Read', name: 'Read' }, { tool: 'Bash', name: 'Bash' }, { tool: 'Read', name: 'Grep' }])
  apply(Object.assign({ type: 'tool', id: 'w3' }, ev));
out.hist = h.acts.map(a => a.text);

// a joined member's person: the same plain words, from its relayed line
apply({ type: 'remote', who: 'Cy', device: 'cy-laptop', dev: 'dev-cy', rid: 'acme/app', br: 'main',
        ev: { type: 'spawn', id: 'r:dev-cy:s:7', role: 'worker', label: 'worker', task: '改支付重试', terr: tid } });
tick(20);
apply({ type: 'remote', who: 'Cy', device: 'cy-laptop', dev: 'dev-cy', rid: 'acme/app', br: 'main',
        ev: { type: 'tool', id: 'r:dev-cy:s:7', tool: 'Read', name: 'Grep' } });
const ra = byId('r:dev-cy:s:7');
out.remote = { step: ra.step, doing: doingText(ra), action: workAction(ra) };

// the demo's member people (made the way seedDemoRemote makes them) get tool lines too; none while a relay is off
const R1 = { who: '', device: 'pc2', dev: 'dev-pc2', rid: 'acme/shop', br: 'test/checkout' };
const R2 = { who: 'Ann', device: 'ann-laptop', dev: 'dev-ann', rid: 'acme/shop', br: 'feat/payment-retry' };
apply({ type: 'team', host: 'demo-team', state: 'ok', queued: 0 });
apply(Object.assign({ type: 'remote', ev: { type: 'spawn', id: 'r:dev-pc2:s:1', role: 'worker', label: 'worker', task: '写结账测试', terr: tid } }, R1));
apply(Object.assign({ type: 'remote', ev: { type: 'spawn', id: 'r:dev-ann:s:1', role: 'worker', label: 'worker', task: '改支付超时重试', terr: tid } }, R2));
apply(Object.assign({ type: 'remote', ev: { type: 'stuck', id: 'r:dev-ann:s:1', tool: 'AskUserQuestion', question: '要不要自动重试？' } }, R2));
tick(20);
const pc2 = byId('r:dev-pc2:s:1'), ann = byId('r:dev-ann:s:1');
out.demoBefore = { kind: pc2 ? pc2.workKind : 'none' };
demoRemoteTick(DEMO_REMOTE_TOOL_SEC + .1);
out.demo = { found: !!pc2, kind: pc2 ? pc2.workKind : '', action: pc2 ? workAction(pc2) : '', step: pc2 ? pc2.step : '',
             annKind: ann ? ann.workKind : 'none', sec: DEMO_REMOTE_TOOL_SEC };
const at0 = pc2 ? pc2.workAt : 0;
apply({ type: 'team', host: 'demo-team', state: 'off', queued: 0 });
tick(1);
demoRemoteTick(5);
out.demoOff = pc2 ? pc2.workAt === at0 : false;
__out = out;
"""

STEPS_REQUIRED = REQUIRED + ("stepText", "doingText", "demoRemoteTick", "DEMO_REMOTE_TOOL_SEC", "workAction", "TEXT")


class TestPlainWordsOnThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        plan, view = sorted(plan_views().items())[0]
        cls.r = run_sim(STEPS_DRIVER, {"view": view, "cases": [c for c, _ in STEP_CASES], "keys": list(STEP_KEYS),
                                       "longTask": LONG_TASK}, STEPS_REQUIRED)

    def test_every_tool_in_plain_words(self):
        for (ev, want), got in zip(STEP_CASES, self.r["steps"]):
            with self.subTest(ev=ev):
                self.assertEqual(got, want)

    def test_words_in_both_languages(self):
        for key, (zh, en) in STEP_KEYS.items():
            with self.subTest(key=key):
                self.assertEqual(self.r["zh"][key], zh)
                self.assertEqual(self.r["en"][key], en)
                self.assertEqual(text_keys(key), 2)

    def test_head_says_task_and_step_while_it_works(self):
        self.assertEqual(self.r["before"], "", "no tool event yet: nothing over the head")
        self.assertEqual(self.r["step"], "改 checkout.py")
        self.assertEqual(self.r["doing"], "写结账测试 · 改 checkout.py")
        self.assertEqual(self.r["paused"], "", "the short pause: nothing over the head")
        self.assertEqual(self.r["doingBash"], "写结账测试 · 跑命令")

    def test_long_task_is_cut_and_a_label_task_is_left_out(self):
        self.assertEqual(self.r["longTask"], LONG_TASK[:13] + "… · 看文件")
        self.assertEqual(self.r["labelTask"], "找代码")

    def test_history_says_steps_not_tool_counts(self):
        self.assertEqual(self.r["hist"], ["看文件 · 跑命令 · 找代码"],
                         "one line for tools in a row, its last 3 plain-words steps")
        for line in self.r["hist"]:
            with self.subTest(line=line):
                self.assertNotRegex(line, r"×|\bx\d|Edit|Read|Bash|Write|Grep")

    def test_other_members_show_plain_words_too(self):
        r = self.r["remote"]
        self.assertEqual(r["step"], "找代码")
        self.assertEqual(r["action"], "read")
        self.assertEqual(r["doing"], "改支付重试 · 找代码")

    def test_demo_member_people_act_too(self):
        d = self.r["demo"]
        self.assertTrue(d["found"], "the pc2 member person")
        self.assertEqual(self.r["demoBefore"]["kind"], "", "no tool line before the tick")
        self.assertIn(d["kind"], ("read", "build", "bash"))
        self.assertNotEqual(d["action"], "", "it acts out its work")
        self.assertNotEqual(d["step"], "")
        self.assertEqual(d["annKind"], "", "a stuck member person gets no tool line")
        self.assertAlmostEqual(d["sec"], 1.6)
        self.assertTrue(self.r["demoOff"], "no tool line while the relay is off")


class TestHeadLine3D(unittest.TestCase):
    def test_update_person_pins_the_doing_line(self):
        up = function_source("updatePerson") or ""
        self.assertIn("doingText(", up)
        self.assertRegex(page(), r"\.doing\{", "a .doing CSS rule")

    def test_update_calls_the_demo_tick(self):
        self.assertRegex(function_source("update") or "", r"DEMO[^\n]*demoRemoteTick\(")


if __name__ == "__main__":
    unittest.main()
