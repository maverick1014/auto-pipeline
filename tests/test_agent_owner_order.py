"""Failing tests for owner-relay: bin/agent-owner-order.sh + bin/agent_owner_order.py.

Written by the task manager before any code. Rules: requirements/owner-relay.md
(owner: rules yes 2026-11-24, every default). Row ids (A1, D5, H14, L4 ...) are
the rows of that file.

Every transcript here is made up. No real transcript text.
A fake $HOME holds the config homes: ~/.claude, an Orca profile home, and
$CLAUDE_CONFIG_DIR when a test sets it. TZ is Asia/Kuala_Lumpur (+08:00, no DST),
AGENT_FAKE_HOST is "test-host" unless a test says otherwise.

Run: python3 -m unittest tests.test_agent_owner_order
"""

import datetime
import itertools
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
import unicodedata
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scripthelp import ScriptCase  # noqa: E402
import agent_conf  # noqa: E402

SCRIPT = "agent-owner-order.sh"
TZ = "Asia/Kuala_Lumpur"
HOST = "test-host"

QUOTE = "keep it, this features is needed ya"
LONG = ("Some other notes here. keep it, this features is needed ya. because it can make "
        "the cross communication more reliable")
LONG_SNIPPET = "…e other notes here. keep it, this features is needed ya. because it can make the…"
NOT_FOUND = "OWNER ORDER not verified: not found (paraphrased, or typed on another machine?)"

_ids = itertools.count(1)


# ------------------------------------------------------------------ helpers

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def ago(minutes=0, hours=0):
    return utc_now() - datetime.timedelta(minutes=minutes, hours=hours)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def minute(dt):
    """The minute the tool prints for a timestamp (local time, TZ +08:00)."""
    return (dt + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")


def hhmm(dt):
    return minute(dt)[11:]


def folder_name(path):
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def _base(kind, dt, **extra):
    line = {"parentUuid": None, "isSidechain": False, "type": kind,
            "uuid": "u-%d" % next(_ids), "timestamp": iso(dt),
            "userType": "external", "sessionId": "s1", "version": "2.1.331"}
    line.update(extra)
    return line


def owner(text, dt, source="typed"):
    """A prompt the owner typed (or queued while the session was busy)."""
    return _base("user", dt, message={"role": "user", "content": text},
                 origin={"kind": "human"}, promptSource=source, turnOrigin="human")


def owner_list(items, dt):
    return _base("user", dt, message={"role": "user", "content": items},
                 origin={"kind": "human"}, promptSource="typed", turnOrigin="human")


def peer(text, dt):
    return _base("user", dt, message={"role": "user",
                                      "content": "Another Claude session sent a message: " + text},
                 isMeta=True,
                 origin={"kind": "peer", "from": "uds:/tmp/cc-socks/1.sock", "verifiedPeerPid": 1,
                         "name": "v4-plus Manager", "fromMode": "bypass", "body": text,
                         "verifiedLocal": True},
                 promptSource="system", turnOrigin="peer")


def tool_result(content, dt):
    return _base("user", dt, message={"role": "user", "content": [
        {"tool_use_id": "t-1", "type": "tool_result", "content": content, "is_error": False}]},
        toolUseResult={"stdout": "x", "stderr": "", "interrupted": False})


def meta(text, dt):
    return _base("user", dt, message={"role": "user", "content": [{"type": "text", "text": text}]},
                 isMeta=True)


def compact(text, dt):
    return _base("user", dt, message={"role": "user",
                                      "content": "This session is being continued. " + text},
                 isCompactSummary=True, isVisibleInTranscriptOnly=True)


def notification(text, dt):
    return _base("user", dt, message={"role": "user",
                                      "content": "<task-notification>" + text + "</task-notification>"},
                 origin={"kind": "task-notification", "producer": "session-task", "runId": "r1"},
                 promptSource="system", turnOrigin="task_notification")


def sdk(text, dt):
    return _base("user", dt, message={"role": "user", "content": text},
                 promptSource="sdk", turnOrigin="sdk")


def assistant(text, dt):
    return _base("assistant", dt, message={"role": "assistant", "content": [
        {"type": "thinking", "thinking": "hm"}, {"type": "text", "text": text}]})


def no_origin(text, dt):
    return _base("user", dt, message={"role": "user", "content": text})


def sidechain(text, dt):
    line = owner(text, dt)
    line["isSidechain"] = True
    return line


def pasted(inner, typed=""):
    return '<pasted_content id="p1">' + inner + "</pasted_content>" + typed


class OwnerOrderCase(ScriptCase):
    script = SCRIPT

    def setUp(self):
        super().setUp()
        self.home = self.repo.fake_home()
        self.sender = self.repo.make_project("sender-repo")
        self.sleepers = []

    def tearDown(self):
        for p in self.sleepers:
            p.kill()
            p.wait()

    # ---- fixture transcripts ----

    def projects(self, where="claude"):
        if where == "claude":
            return os.path.join(self.home, ".claude", "projects")
        if where == "orca":
            return os.path.join(self.home, "Library", "Application Support", "orca",
                                "claude-profiles", "p1", "home", "projects")
        if where == "config":
            return os.path.join(self.repo.base, "cfg", "projects")
        raise ValueError(where)

    def write(self, lines, repo=None, name="s1.jsonl", where="claude", mtime=None, raw_tail=None):
        folder = os.path.join(self.projects(where), folder_name(repo or self.sender))
        os.makedirs(os.path.dirname(os.path.join(folder, name)), exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            if raw_tail is not None:
                fh.write(raw_tail)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def shown(self, path):
        """How the tool prints a file path: $HOME as ~."""
        if path.startswith(self.home + os.sep):
            return "~" + path[len(self.home):]
        return path

    # ---- runs ----

    def env(self, extra=None):
        e = {"TZ": TZ, "AGENT_FAKE_HOST": HOST}
        e.update(extra or {})
        return e

    def run_tool(self, *args, env=None, cwd=None):
        return self.repo.run(SCRIPT, *args, env=self.env(env), cwd=cwd)

    def verify(self, quote=QUOTE, *extra, repo=None, env=None):
        return self.run_tool("verify", "--repo", repo or self.sender, "--quote", quote, *extra, env=env)

    def out_lines(self, result):
        return result.stdout.rstrip("\n").split("\n") if result.stdout.strip() else []

    def assertVerified(self, result, path, dt):
        self.assertEqual(result.returncode, 0,
                         "exit %d\nSTDOUT:\n%s\nSTDERR:\n%s" % (result.returncode, result.stdout, result.stderr))
        self.assertEqual(self.out_lines(result)[0],
                         "OWNER ORDER verified %s %s" % (self.shown(path), minute(dt)))

    def assertRefused(self, result, line):
        self.assertEqual(result.returncode, 1,
                         "exit %d\nSTDOUT:\n%s\nSTDERR:\n%s" % (result.returncode, result.stdout, result.stderr))
        self.assertEqual(self.out_lines(result), [line])

    def assertReason(self, result, *parts):
        self.assertEqual(result.returncode, 1,
                         "exit %d\nSTDOUT:\n%s\nSTDERR:\n%s" % (result.returncode, result.stdout, result.stderr))
        lines = self.out_lines(result)
        self.assertEqual(len(lines), 1, result.stdout)
        self.assertTrue(lines[0].startswith("OWNER ORDER not verified: "), lines[0])
        for part in parts:
            self.assertIn(part, lines[0])
        return lines[0]

    def assertUsage(self, result):
        self.assertEqual(result.returncode, 2,
                         "exit %d\nSTDOUT:\n%s\nSTDERR:\n%s" % (result.returncode, result.stdout, result.stderr))
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)

    def sleeper(self, *args):
        """A live process whose command line holds ARGS: the session pid for `line`."""
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"] + list(args))
        self.sleepers.append(p)
        time.sleep(0.2)
        return str(p.pid)


# ================================================================== D. verify: found

class TestVerifyFound(OwnerOrderCase):

    def test_d2_one_owner_prompt_is_verified_with_file_minute_and_snippet(self):
        dt = ago(30)
        path = self.write([owner(LONG, dt)])
        r = self.verify()
        self.assertVerified(r, path, dt)
        self.assertEqual(self.out_lines(r), [
            "OWNER ORDER verified %s %s" % (self.shown(path), minute(dt)),
            'match: "%s"' % LONG_SNIPPET,
        ])

    def test_d2_home_shows_as_tilde(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        line = self.out_lines(self.verify())[0]
        self.assertIn(" ~/.claude/projects/%s/s1.jsonl " % folder_name(self.sender), line)

    def test_f2_short_prompt_snippet_has_no_dots(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        self.assertEqual(self.out_lines(self.verify())[1], 'match: "%s"' % QUOTE)

    def test_c1_whitespace_is_normalised_on_both_sides(self):
        dt = ago(30)
        path = self.write([owner("keep it,  this features\nis needed ya.", dt)])
        self.assertVerified(self.verify(" keep it, this\tfeatures is needed  ya "), path, dt)

    def test_c1_unicode_nfc_on_both_sides(self):
        dt = ago(30)
        words = "the café order must ship today ok"
        path = self.write([owner(unicodedata.normalize("NFD", words), dt)])
        self.assertVerified(self.verify(unicodedata.normalize("NFC", words)), path, dt)

    def test_h5_case_counts(self):
        self.write([owner("Keep it, this features is needed ya", ago(30))])
        self.assertRefused(self.verify(), NOT_FOUND)

    def test_h3_paraphrase_is_not_found(self):
        self.write([owner(QUOTE, ago(30))])
        self.assertRefused(self.verify("keep it, this feature is needed ya"), NOT_FOUND)

    def test_c2_quote_inside_a_longer_prompt(self):
        dt = ago(30)
        path = self.write([owner("first line\n" + LONG + "\nlast line", dt)])
        self.assertVerified(self.verify(), path, dt)

    def test_h23_queued_prompt_is_an_owner_prompt(self):
        dt = ago(30)
        path = self.write([owner(QUOTE, dt, source="queued")])
        self.assertVerified(self.verify(), path, dt)

    def test_h24_list_content_uses_the_text_items(self):
        dt = ago(30)
        path = self.write([owner_list([
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}},
            {"type": "text", "text": LONG}], dt)])
        self.assertVerified(self.verify(), path, dt)

    def test_h27_any_session_file_of_the_folder(self):
        dt = ago(30)
        self.write([owner("an unrelated prompt of the first session", ago(50))], name="s1.jsonl")
        path = self.write([owner(QUOTE, dt)], name="s2.jsonl")
        self.assertVerified(self.verify(), path, dt)

    def test_l9_owner_prompt_wins_over_a_peer_line(self):
        dt = ago(30)
        path = self.write([peer(QUOTE, ago(20)), owner(QUOTE, dt)])
        self.assertVerified(self.verify(), path, dt)

    def test_b3_header_on_the_second_line_is_still_the_owner(self):
        dt = ago(30)
        path = self.write([owner("please do this now\n[Opus 5.5 xhigh] " + QUOTE, dt)])
        self.assertVerified(self.verify(), path, dt)

    def test_b3_a_model_word_without_brackets_is_the_owner(self):
        dt = ago(30)
        path = self.write([owner("please use opus for this whole task today", dt)])
        self.assertVerified(self.verify("please use opus for this whole task today"), path, dt)

    def test_l1_pasted_brief_with_a_header_then_typed_words_is_the_owner(self):
        dt = ago(30)
        path = self.write([owner(pasted("[Opus 5.5 xhigh] Brief from the main manager", "\n" + QUOTE), dt)])
        self.assertVerified(self.verify(), path, dt)


# ================================================================== A. where

class TestWhere(OwnerOrderCase):

    def test_h18_orca_profile_home(self):
        dt = ago(30)
        path = self.write([owner(QUOTE, dt)], where="orca")
        self.assertVerified(self.verify(), path, dt)

    def test_h19_claude_config_dir(self):
        dt = ago(30)
        path = self.write([owner(QUOTE, dt)], where="config")
        cfg = os.path.dirname(self.projects("config"))
        r = self.verify(env={"CLAUDE_CONFIG_DIR": cfg})
        self.assertVerified(r, path, dt)
        self.assertIn(" %s " % path, self.out_lines(r)[0])

    def test_a1_real_path_of_a_link(self):
        dt = ago(30)
        link = os.path.join(self.repo.base, "link-to-sender")
        os.symlink(self.sender, link)
        path = self.write([owner(QUOTE, dt)])          # folder named by the real path
        self.assertVerified(self.verify(repo=link), path, dt)

    def test_a1_folder_named_by_the_given_path(self):
        dt = ago(30)
        link = os.path.join(self.repo.base, "link-to-sender")
        os.symlink(self.sender, link)
        path = self.write([owner(QUOTE, dt)], repo=link)
        self.assertVerified(self.verify(repo=link), path, dt)

    def test_a3_tilde_and_trailing_slash(self):
        dt = ago(30)
        repo = os.path.join(self.home, "work", "v4")
        os.makedirs(repo)
        path = self.write([owner(QUOTE, dt)], repo=repo)
        self.assertVerified(self.verify(repo="~/work/v4/"), path, dt)

    def test_a2_a_file_changed_before_the_window_is_not_opened(self):
        self.write([owner(QUOTE, ago(30))], mtime=time.time() - 3 * 86400)
        self.assertRefused(self.verify(), NOT_FOUND)

    def test_h20_a_half_written_line_is_skipped(self):
        dt = ago(30)
        path = self.write([owner(QUOTE, dt)], raw_tail='{"type":"user","message":{"role":"us')
        self.assertVerified(self.verify(), path, dt)

    def test_a2_a_broken_line_in_the_middle_is_skipped(self):
        dt = ago(30)
        path = self.write([owner("an earlier prompt here", ago(40))],
                          raw_tail="not json at all\n" + json.dumps(owner(QUOTE, dt)) + "\n")
        self.assertVerified(self.verify(), path, dt)

    def test_a4_no_project_folder(self):
        r = self.verify()
        line = self.assertReason(r, "no transcript for %s on this machine (looked in: " % self.sender)
        self.assertTrue(line.endswith(")"), line)

    def test_h26_subagent_files_are_not_read(self):
        self.write([owner("an earlier prompt here", ago(40))])
        self.write([owner(QUOTE, ago(30))], name=os.path.join("s1", "subagents", "agent-a1.jsonl"))
        self.assertRefused(self.verify(), NOT_FOUND)

    def test_c5_same_minute_in_two_files_is_one_match_newest_file(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)], name="old.jsonl", mtime=time.time() - 600)
        newer = self.write([owner(QUOTE, dt)], name="new.jsonl")
        self.assertVerified(self.verify(), newer, dt)

    def test_c5_same_minute_in_two_homes_is_one_match(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)], where="orca", mtime=time.time() - 600)
        newer = self.write([owner(QUOTE, dt)], where="claude")
        self.assertVerified(self.verify(), newer, dt)


# ================================================================== B. kinds

class TestKinds(OwnerOrderCase):

    def only_in(self, lines, kind_text, quote=QUOTE):
        path = self.write(lines)
        r = self.verify(quote)
        return self.assertReason(r, "only in a", kind_text, self.shown(path))

    def test_h6_peer(self):
        dt = ago(30)
        path = self.write([peer(QUOTE, dt)])
        self.assertRefused(self.verify(),
                           "OWNER ORDER not verified: only in a peer line (%s %s)" % (self.shown(path), minute(dt)))

    def test_h7_tool_result_string_content(self):
        self.only_in([tool_result("file text: " + QUOTE, ago(30))], "tool_result line")

    def test_l3_tool_result_list_content(self):
        self.only_in([tool_result([{"type": "text", "text": "file text: " + QUOTE}], ago(30))],
                     "tool_result line")

    def test_h8_meta(self):
        self.only_in([meta("Base directory for this skill: " + QUOTE, ago(30))], "meta line")

    def test_h9_compact_summary(self):
        self.only_in([compact(QUOTE, ago(30))], "compact summary line")

    def test_b2_task_notification(self):
        self.only_in([notification(QUOTE, ago(30))], "task notification line")

    def test_b2_sdk_prompt_is_system(self):
        self.only_in([sdk(QUOTE, ago(30))], "system line")

    def test_h10_assistant(self):
        r = self.only_in([assistant("I will relay: " + QUOTE, ago(30))], "assistant line")
        self.assertIn("only in an assistant line", r)

    def test_h11_agent_typed_header_first(self):
        r = self.only_in([owner("[Opus 5.5 xhigh] Brief: " + QUOTE, ago(30))], "agent-typed line")
        self.assertIn("only in an agent-typed line", r)

    def test_h11_agent_typed_header_after_a_name(self):
        self.only_in([owner("v4-plus Manager [Opus 5.5 xhigh] ANSWER " + QUOTE, ago(30))], "agent-typed line")

    def test_h11_agent_typed_header_with_a_role(self):
        self.only_in([owner("[main manager, Opus 5.5 xhigh] " + QUOTE, ago(30))], "agent-typed line")

    def test_b3_any_case_and_other_families(self):
        for head in ("[sonnet 5 medium]", "[HAIKU 5.5 low]", "[Fable 5.2 high]"):
            with self.subTest(head=head):
                path = self.write([owner(head + " " + QUOTE, ago(30))])
                self.assertReason(self.verify(), "agent-typed line")
                os.unlink(path)

    def test_b3_leading_blank_lines_are_skipped(self):
        self.only_in([owner("\n\n  [Opus 5.5 xhigh] " + QUOTE, ago(30))], "agent-typed line")

    def test_h12_pasted(self):
        self.only_in([owner(pasted("a brief that says " + QUOTE, "\nplease read this"), ago(30))],
                     "pasted line")

    def test_b4_unclosed_pasted_block_runs_to_the_end(self):
        self.only_in([owner('please read this\n<pasted_content id="p2">brief: ' + QUOTE, ago(30))],
                     "pasted line")

    def test_h22_no_origin(self):
        r = self.only_in([no_origin(QUOTE, ago(30))], "other line")
        self.assertIn("only in an other line", r)

    def test_l2_sidechain_is_other(self):
        self.only_in([sidechain(QUOTE, ago(30))], "other line")

    def test_l4_two_kinds_in_rule_order_newest_hit_shown(self):
        old, new = ago(40), ago(30)
        path = self.write([tool_result(QUOTE, old), peer(QUOTE, new)])
        self.assertRefused(self.verify(),
                           "OWNER ORDER not verified: only in a tool_result, peer line (%s %s)"
                           % (self.shown(path), minute(new)))


# ================================================================== D. time, window, several

class TestTimeAndMany(OwnerOrderCase):

    def test_h13_older_than_the_window(self):
        dt = ago(hours=25)
        self.write([owner(QUOTE, dt)])
        self.assertRefused(self.verify(),
                           "OWNER ORDER not verified: older than 24h (newest %s)" % minute(dt))

    def test_d5_older_wins_over_other_kinds(self):
        dt = ago(hours=25)
        self.write([owner(QUOTE, dt), peer(QUOTE, ago(30))])
        self.assertRefused(self.verify(),
                           "OWNER ORDER not verified: older than 24h (newest %s)" % minute(dt))

    def test_window_edge_inside(self):
        dt = ago(hours=23, minutes=50)
        path = self.write([owner(QUOTE, dt)])
        self.assertVerified(self.verify(), path, dt)

    def test_h14_several_minutes_need_time(self):
        a, b = ago(40), ago(35)
        path = self.write([owner(QUOTE, a), owner("again: " + QUOTE, b)])
        r = self.verify()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        lines = self.out_lines(r)
        self.assertEqual(lines[0], "OWNER ORDER not verified: several owner prompts hold the quote, pass --time")
        self.assertEqual(len(lines), 3, r.stdout)
        self.assertTrue(lines[1].startswith("  %s %s \"" % (self.shown(path), minute(b))), lines[1])
        self.assertTrue(lines[2].startswith("  %s %s \"" % (self.shown(path), minute(a))), lines[2])
        self.assertTrue(lines[1].endswith('"') and lines[2].endswith('"'))

    def test_d3_time_hh_mm_picks_one(self):
        a, b = ago(40), ago(35)
        path = self.write([owner(QUOTE, a), owner("again: " + QUOTE, b)])
        self.assertVerified(self.verify(QUOTE, "--time", hhmm(a)), path, a)

    def test_d3_time_full_minute_picks_one(self):
        a, b = ago(40), ago(35)
        path = self.write([owner(QUOTE, a), owner("again: " + QUOTE, b)])
        self.assertVerified(self.verify(QUOTE, "--time", minute(b)), path, b)

    def test_h25_no_owner_prompt_at_that_time(self):
        a, at = ago(40), hhmm(ago(35))
        self.write([owner(QUOTE, a)])
        self.assertRefused(self.verify(QUOTE, "--time", at),
                           "OWNER ORDER not verified: no owner prompt at %s (found at %s)" % (at, minute(a)))

    def test_l6_found_at_lists_newest_first(self):
        a, b = ago(40), ago(35)
        self.write([owner(QUOTE, a), owner("again: " + QUOTE, b)])
        at = hhmm(ago(30))
        self.assertRefused(self.verify(QUOTE, "--time", at),
                           "OWNER ORDER not verified: no owner prompt at %s (found at %s, %s)"
                           % (at, minute(b), minute(a)))

    def test_d3_time_does_not_hide_a_single_good_match(self):
        dt = ago(30)
        path = self.write([owner(QUOTE, dt)])
        self.assertVerified(self.verify(QUOTE, "--time", hhmm(dt)), path, dt)


# ================================================================== C. length, usage

class TestShortAndUsage(OwnerOrderCase):

    def test_h21_too_short_before_any_search(self):
        self.assertRefused(self.verify("rules yes"),
                           "OWNER ORDER not verified: quote too short (9 < 20)")

    def test_c3_wide_characters_count_two(self):
        self.assertRefused(self.verify("这个功能很重要"),
                           "OWNER ORDER not verified: quote too short (14 < 20)")

    def test_c3_wide_quote_long_enough(self):
        dt = ago(30)
        words = "这个功能需要保留很重要"
        path = self.write([owner("老板说: " + words + "。", dt)])
        self.assertVerified(self.verify(words), path, dt)

    def test_c3_width_counts_after_normalise(self):
        self.assertRefused(self.verify("  rules     yes   "),
                           "OWNER ORDER not verified: quote too short (9 < 20)")

    def test_c4_empty_quote_is_a_usage_error(self):
        self.assertUsage(self.verify("   "))

    def test_d7_usage_errors(self):
        cases = [
            ("verify", "--quote", QUOTE),                                  # no --repo
            ("verify", "--repo", self.sender),                             # no --quote
            ("verify", "--repo", self.sender, "--quote", QUOTE, "--time", "25:99"),
            ("verify", "--repo", self.sender, "--quote", QUOTE, "--time", "yesterday"),
            ("verify", "--repo", self.sender, "--quote", QUOTE, "--bogus", "x"),
            ("verify", "--repo"),                                          # option without value
            ("frobnicate",),
            (),
            ("line",),                                                     # line without --quote
        ]
        for args in cases:
            with self.subTest(args=args):
                self.assertUsage(self.run_tool(*args))


# ================================================================== D1. machine

class TestMachine(OwnerOrderCase):

    def test_d1_another_machine_reads_nothing(self):
        self.assertRefused(self.verify(QUOTE, "--machine", "other-host"),
                           "OWNER ORDER not verified: sender on another machine (other-host, this is test-host)")

    def test_d1_same_machine_goes_on(self):
        dt = ago(30)
        path = self.write([owner(QUOTE, dt)])
        self.assertVerified(self.verify(QUOTE, "--machine", HOST), path, dt)

    def test_l5_real_machine_name_without_the_switch(self):
        if platform.system() == "Darwin":
            name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True,
                                  text=True).stdout.strip()
        else:
            name = subprocess.run(["hostname", "-s"], capture_output=True, text=True).stdout.strip()
        dt = ago(30)
        path = self.write([owner(QUOTE, dt)])
        self.assertVerified(self.verify(QUOTE, "--machine", name, env={"AGENT_FAKE_HOST": ""}), path, dt)


# ================================================================== F. privacy

class TestPrivacy(OwnerOrderCase):

    def test_f1_f2_long_prompt_prints_at_most_80_characters(self):
        dt = ago(30)
        head = " ".join("HEADWORD%02d" % i for i in range(20))
        tail = " ".join("TAILWORD%02d" % i for i in range(20))
        self.write([owner(head + " " + QUOTE + " " + tail, dt)])
        r = self.verify()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        snippet = self.out_lines(r)[1]
        self.assertTrue(snippet.startswith('match: "…') and snippet.endswith('…"'), snippet)
        inner = snippet[len('match: "…'):-len('…"')]
        self.assertEqual(len(inner), 80, inner)
        self.assertIn(QUOTE, inner)
        self.assertNotIn("HEADWORD00", r.stdout)
        self.assertNotIn("TAILWORD19", r.stdout)

    def test_f1_other_lines_are_never_printed(self):
        dt = ago(30)
        self.write([owner("PRIVATE-OTHER-WORDS of an earlier prompt", ago(50)),
                    peer("PRIVATE-PEER-WORDS", ago(45)),
                    owner(QUOTE, dt)])
        r = self.verify()
        self.assertNotIn("PRIVATE", r.stdout + r.stderr)

    def test_f3_read_only(self):
        self.write([owner(QUOTE, ago(30))])

        def snap():
            out = {}
            for top in (self.home, self.repo.dir, self.sender):
                for d, dirs, files in os.walk(top):
                    if ".git" in d.split(os.sep):
                        continue
                    for f in files:
                        p = os.path.join(d, f)
                        out[p] = os.stat(p).st_mtime_ns
            return out

        before = snap()
        self.verify()
        self.verify("rules yes")
        self.assertEqual(snap(), before)


# ================================================================== E. line (sender)

class TestLine(OwnerOrderCase):

    def setUp(self):
        super().setUp()
        self.repo.git_init(self.sender)

    def line(self, quote=QUOTE, *extra, env=None, cwd=None, pid_args=()):
        e = {"CLAUDE_PID": self.sleeper(*pid_args)}
        e.update(env or {})
        return self.run_tool("line", "--quote", quote, *extra, env=e, cwd=cwd or self.sender)

    def test_e3_three_lines(self):
        dt = ago(30)
        self.write([owner(LONG, dt)])
        r = self.line(env={"ANTHROPIC_MODEL": "opus", "CLAUDE_CODE_EFFORT_LEVEL": "xhigh"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = self.out_lines(r)
        self.assertEqual(len(lines), 3, r.stdout)
        self.assertEqual(lines[0], "OWNER ORDER [opus xhigh] repo %s · machine %s · typed %s"
                         % (self.sender, HOST, minute(dt)))
        self.assertEqual(lines[1], '"%s"' % QUOTE)
        self.assertTrue(lines[2].startswith("check: "), lines[2])
        self.assertEqual(shlex.split(lines[2][len("check: "):]),
                         ["agent-owner-order.sh", "verify", "--repo", self.sender, "--machine", HOST,
                          "--time", minute(dt), "--quote", QUOTE])

    def test_e3_quote_line_is_the_normalised_quote(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        r = self.line("  keep it,\nthis features is   needed ya ")
        self.assertEqual(self.out_lines(r)[1], '"%s"' % QUOTE)

    def test_e4_flags_of_the_session_process(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        r = self.line(pid_args=("--model", "fable", "--effort", "high"))
        self.assertTrue(self.out_lines(r)[0].startswith("OWNER ORDER [fable high] repo "), r.stdout)

    def test_e4_nothing_known_is_the_setting_default(self):
        # settings-configure: the Main manager model setting always has a value (default opus-5.5:high)
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        r = self.line()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.out_lines(r)[0].startswith("OWNER ORDER [opus-5.5 high] repo "), r.stdout)

    def test_e4_the_main_manager_setting(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        self.repo.set_conf("main_manager", "opus-5.5:xhigh")
        r = self.line()
        self.assertTrue(self.out_lines(r)[0].startswith("OWNER ORDER [opus-5.5 xhigh] repo "), r.stdout)

    def test_e1_from_a_sub_folder(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        sub = os.path.join(self.sender, "deep", "er")
        os.makedirs(sub)
        r = self.line(cwd=sub)
        self.assertIn(" repo %s · " % self.sender, self.out_lines(r)[0])

    def test_e1_claude_project_dir_wins_over_pwd(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        r = self.line(env={"CLAUDE_PROJECT_DIR": self.sender}, cwd=self.repo.dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(" repo %s · " % self.sender, self.out_lines(r)[0])

    def test_e1_repo_option(self):
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        r = self.line(QUOTE, "--repo", self.sender, cwd=self.repo.dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(" repo %s · " % self.sender, self.out_lines(r)[0])

    def test_e2_several_takes_the_newest(self):
        a, b = ago(40), ago(35)
        self.write([owner(QUOTE, a), owner("again: " + QUOTE, b)])
        r = self.line()
        self.assertTrue(self.out_lines(r)[0].endswith(" · typed %s" % minute(b)), r.stdout)

    def test_e5_not_found_prints_no_header(self):
        self.write([owner("something else entirely here", ago(30))])
        r = self.line()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.out_lines(r),
                         ["OWNER ORDER not found: not found (paraphrased, or typed on another machine?)"])

    def test_e5_too_short(self):
        r = self.line("rules yes")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.out_lines(r), ["OWNER ORDER not found: quote too short (9 < 20)"])

    def test_e5_only_in_a_peer_line(self):
        dt = ago(30)
        path = self.write([peer(QUOTE, dt)])
        r = self.line()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.out_lines(r),
                         ["OWNER ORDER not found: only in a peer line (%s %s)" % (self.shown(path), minute(dt))])

    def test_e5_no_transcript(self):
        r = self.line()
        self.assertEqual(r.returncode, 1)
        self.assertTrue(self.out_lines(r)[0].startswith(
            "OWNER ORDER not found: no transcript for %s on this machine (looked in: " % self.sender), r.stdout)

    def test_h29_check_line_runs_as_is_with_quotes_and_dollar(self):
        dt = ago(30)
        words = "don't touch \"prod\" until $HOME is set, ok?"
        self.write([owner(words, dt)])
        r = self.line(words)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        check = self.out_lines(r)[2][len("check: "):]
        self.assertTrue(check.startswith("agent-owner-order.sh "), check)
        cmd = shlex.quote(self.repo.script_path(SCRIPT)) + check[len("agent-owner-order.sh"):]
        env = self.repo._env(self.env())
        v = subprocess.run(["bash", "-c", cmd], cwd=self.repo.dir, env=env, capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertTrue(v.stdout.startswith("OWNER ORDER verified "), v.stdout)



# ================================================================== review bounce 1 (L10-L16)

class TestReviewBounce1(OwnerOrderCase):

    def test_l10_a_paste_holding_a_closing_tag(self):
        self.write([owner(pasted("doc says </pasted_content> " + QUOTE + " more", " ok read"), ago(30))])
        self.assertReason(self.verify(), "pasted line")

    def test_l10_a_nested_paste(self):
        self.write([owner('<pasted_content id="p1">a <pasted_content id="p2">b</pasted_content> '
                          + QUOTE + ' </pasted_content> please read', ago(30))])
        self.assertReason(self.verify(), "pasted line")

    def test_l10_two_clean_pastes_with_typed_words_between_verify(self):
        dt = ago(30)
        path = self.write([owner(pasted("first doc") + " " + QUOTE + " " + pasted("second doc"), dt)])
        self.assertVerified(self.verify(), path, dt)

    def test_l11_a_relayed_header_typed_into_a_pane(self):
        self.write([owner("OWNER ORDER [unknown unknown] repo /x · machine h · typed 2026-11-24 11:42\n\"%s\"" % QUOTE,
                          ago(30))])
        self.assertReason(self.verify(), "agent-typed line")

    def test_l11_the_words_owner_order_later_in_the_line_are_fine(self):
        dt = ago(30)
        path = self.write([owner("please send an OWNER ORDER: " + QUOTE, dt)])
        self.assertVerified(self.verify(), path, dt)

    def test_l12_verify_needs_an_absolute_repo(self):
        for repo in ("", ".", "sender-repo", "./sender-repo"):
            with self.subTest(repo=repo):
                self.assertUsage(self.run_tool("verify", "--repo", repo, "--quote", QUOTE,
                                               cwd=self.repo.base))

    def test_l12_line_makes_the_repo_absolute(self):
        self.repo.git_init(self.sender)
        dt = ago(30)
        self.write([owner(QUOTE, dt)])
        r = self.run_tool("line", "--quote", QUOTE, "--repo", ".", cwd=self.sender,
                          env={"CLAUDE_PID": self.sleeper()})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = self.out_lines(r)
        self.assertIn(" repo %s · " % self.sender, lines[0])
        argv = shlex.split(lines[2][len("check: "):])
        self.assertEqual(argv[argv.index("--repo") + 1], self.sender)

    def stamped(self, text, stamp):
        line = owner(text, ago(30))
        line["timestamp"] = stamp
        return line

    def test_l13_offset_timestamp_counts_its_offset(self):
        dt = ago(hours=30)
        stamp = (dt + datetime.timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S.000+08:00")
        self.write([self.stamped(QUOTE, stamp)])
        self.assertRefused(self.verify(),
                           "OWNER ORDER not verified: older than 24h (newest %s)" % minute(dt))

    def test_l13_offset_timestamp_inside_the_window(self):
        dt = ago(30)
        stamp = (dt + datetime.timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S+08:00")
        path = self.write([self.stamped(QUOTE, stamp)])
        self.assertVerified(self.verify(), path, dt)

    def test_l13_no_zone_missing_or_bad_is_skipped(self):
        no_zone = ago(30).strftime("%Y-%m-%dT%H:%M:%S.000")
        for stamp in (no_zone, None, "yesterday", ""):
            with self.subTest(stamp=stamp):
                line = self.stamped(QUOTE, stamp)
                if stamp is None:
                    del line["timestamp"]
                self.write([line])
                self.assertRefused(self.verify(), NOT_FOUND)

    def test_l13_future_is_skipped(self):
        self.write([self.stamped(QUOTE, iso(utc_now() + datetime.timedelta(hours=5)))])
        self.assertRefused(self.verify(), NOT_FOUND)

    def test_l14_word_edge_at_the_start(self):
        self.write([owner("undelete all the old branches now please", ago(30))])
        self.assertRefused(self.verify("delete all the old branches now"), NOT_FOUND)

    def test_l14_word_edge_at_the_end(self):
        self.write([owner("keep it, this features is needed yay", ago(30))])
        self.assertRefused(self.verify(), NOT_FOUND)

    def test_l14_punctuation_is_an_edge(self):
        dt = ago(30)
        path = self.write([owner("(" + QUOTE + ")", dt)])
        self.assertVerified(self.verify(), path, dt)

    def test_l14_a_quote_ending_in_punctuation_needs_no_edge_after(self):
        dt = ago(30)
        path = self.write([owner(QUOTE + ".Next sentence", dt)])
        self.assertVerified(self.verify(QUOTE + "."), path, dt)

    def test_l14_cjk_inside_a_sentence(self):
        dt = ago(30)
        words = "这个功能需要保留很重要"
        path = self.write([owner("老板说" + words + "啊", dt)])
        self.assertVerified(self.verify(words), path, dt)

    def test_l15_flags_set_by_any_true_value(self):
        for flag, value, kind in (("isMeta", 1, "meta line"), ("isMeta", "true", "meta line"),
                                  ("isCompactSummary", "true", "compact summary line"),
                                  ("isSidechain", 1, "other line")):
            with self.subTest(flag=flag, value=value):
                line = owner(QUOTE, ago(30))
                line[flag] = value
                self.write([line])
                self.assertReason(self.verify(), kind)

    def test_l15_false_and_null_flags_are_not_set(self):
        dt = ago(30)
        line = owner(QUOTE, dt)
        line.update({"isMeta": False, "isCompactSummary": None, "isSidechain": False})
        path = self.write([line])
        self.assertVerified(self.verify(), path, dt)

    def test_b1_owner_shaped_lines_with_one_bad_mark(self):
        """origin human + typed, plus one mark that B1 refuses (review finding 6)."""
        def with_mark(mark):
            line = owner(QUOTE, ago(30))
            if mark == "meta":
                line["isMeta"] = True
            elif mark == "compact":
                line["isCompactSummary"] = True
            elif mark == "result key":
                line["toolUseResult"] = {"stdout": ""}
            elif mark == "result item":
                line["message"]["content"] = [{"type": "tool_result", "tool_use_id": "t", "content": QUOTE}]
            return line
        for mark, kind in (("meta", "meta line"), ("compact", "compact summary line"),
                           ("result key", "tool_result line"), ("result item", "tool_result line")):
            with self.subTest(mark=mark):
                self.write([with_mark(mark)])
                self.assertReason(self.verify(), kind)

    def test_l16_a_too_deep_line_is_skipped(self):
        dt = ago(30)
        path = self.write([owner(QUOTE, dt)], raw_tail="[" * 200000 + "\n")
        r = self.verify()
        self.assertNotIn("Traceback", r.stderr)
        self.assertVerified(r, path, dt)

    def test_l16_bytes_that_are_not_utf8(self):
        bad = os.fsdecode(b"/tmp/no-such-\xff-repo")
        r = self.verify(QUOTE, repo=bad)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertTrue(r.stdout.startswith("OWNER ORDER not verified: no transcript for "), r.stdout)
        r = self.verify(QUOTE, "--machine", os.fsdecode(b"host-\xff"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertTrue(r.stdout.startswith("OWNER ORDER not verified: sender on another machine ("), r.stdout)

    def test_c1_a_quote_over_two_owner_lines_is_not_found(self):
        self.write([owner("keep it, this features", ago(31)), owner("is needed ya", ago(30))])
        self.assertRefused(self.verify(), NOT_FOUND)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BIN = os.path.join(ROOT, "bin")


class TestBinPair(unittest.TestCase):

    def test_the_shell_entry_is_executable(self):
        path = os.path.join(BIN, "agent-owner-order.sh")
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.access(path, os.X_OK))

    def test_the_logic_file_is_there(self):
        self.assertTrue(os.path.isfile(os.path.join(BIN, "agent_owner_order.py")))


class TestConfKeys(unittest.TestCase):
    """settings-configure: owner_order_hours and owner_order_min_chars are fixed constants."""

    def test_g4_the_constants(self):
        self.assertEqual(agent_conf.CONSTANTS["owner_order_hours"], 24)
        self.assertEqual(agent_conf.CONSTANTS["owner_order_min_chars"], 20)


if __name__ == "__main__":
    unittest.main()
