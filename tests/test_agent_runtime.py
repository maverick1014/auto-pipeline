"""Failing tests for bin/agent-runtime.sh. Written by the task manager, before any code.

WHY. Orca is one way to run this pipeline, not the only one. The owner is half
Orca, half the Claude app, and a cloud session is a third shape again. Every
place that says `orca` today must ask the runtime instead.

CONTRACT the worker must implement in bin/agent-runtime.sh (executable, and
also safe to source):

    bin/agent-runtime.sh kind                      orca | plain | cloud
    bin/agent-runtime.sh ps                        the worktree JSON, or nothing
    bin/agent-runtime.sh browser                   chrome | headless | none
    bin/agent-runtime.sh launch <path> <title> <command>
    bin/agent-runtime.sh close <handle>
    bin/agent-runtime.sh -h                        usage, exit 0
    no argument, or anything else                  usage, exit 2

Sourced, it defines runtime_kind, runtime_ps, runtime_launch, runtime_close and
runtime_browser, and runs nothing.

KIND. Worked out fresh on every call. Never cached, never written to a file:
the owner switches between Orca and the Claude app inside one day.

    0. $RUNTIME_KIND is orca, plain or cloud          -> that one, full stop
    1. agent.conf `runtime` is orca, plain or cloud   -> that one, full stop
    2. CLAUDE_CODE_REMOTE=true                        -> cloud
    3. orca on PATH and `orca worktree ps --json`
       answers inside 3 seconds                       -> orca
    4. anything else                                  -> plain

$RUNTIME_KIND is a one-shot override, not a cache: it is something a caller
SETS, never something this script writes. It exists for two reasons. A human
can prove either mode without editing agent.conf or uninstalling Orca
(`RUNTIME_KIND=plain bin/agent-resume.sh`). And a script that has already
worked the kind out once can pass it down to the runtime calls it then makes,
instead of paying for the 3-second probe again on every single call. A value
that is not one of the three is ignored, exactly like a bad agent.conf value.

`runtime=auto`, no runtime line, or a value that is not one of the three, all
fall through to step 2.

plain and cloud are the same shape: no terminals, no panes, no monitor loop.
They differ only in the browser.

The probe in step 3 IS `orca worktree ps --json`, so `runtime=orca` in
agent.conf skips it and every verb then makes exactly one orca call. On `auto`
the probe comes first and a verb costs one call more. Any temp file the probe
needs lives under ${TMPDIR:-/tmp} and is gone before the call returns.

PS.
    orca         prints what `orca worktree ps --json` prints, exit 0.
                 orca not answering -> exit 1, nothing on stdout
    plain,cloud  nothing on stdout, exit 0, and orca is never called

LAUNCH.
    orca         orca terminal create --worktree path:<path> --title <title>
                      --command <command> --json
    plain,cloud  cannot open a terminal. Exit non-zero with ONE line on stderr
                 telling the caller to use the Agent tool (a subagent) instead.
                 Never pretend it launched. orca is never called.

CLOSE.
    orca         orca terminal close --terminal <handle> --json
    plain,cloud  nothing to close. Exit 0, no output, orca is never called.

BROWSER. What can actually be driven, never what would be nice.

    orca, plain  "chrome" when the Claude in Chrome native messaging host file
                 is there, else "none". Claude in Chrome needs a local CLI plus
                 the extension; Orca has nothing to do with it. Four places are
                 checked, under $HOME:
                   Library/Application Support/Google/Chrome/NativeMessagingHosts/
                   Library/Application Support/Microsoft Edge/NativeMessagingHosts/
                   .config/google-chrome/NativeMessagingHosts/
                   .config/microsoft-edge/NativeMessagingHosts/
                 file name com.anthropic.claude_code_browser_extension.json
    cloud        Claude in Chrome can never work there: no extension, no native
                 host in the VM. "headless" when chromium, chromium-browser or
                 google-chrome is on PATH, or `npx --no-install playwright
                 --version` exits 0. Else "none". `--no-install` matters: a bare
                 npx would try to download playwright.
"""

import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase

KINDS = ["orca", "plain", "cloud"]
FUNCTIONS = ["runtime_kind", "runtime_ps", "runtime_launch", "runtime_close",
             "runtime_browser"]

NPX_STUB = """#!/usr/bin/env bash
{ printf 'NPX'; for a in "$@"; do printf '\\t%s' "$a"; done; printf '\\n'; } \\
  >> "$NPX_STUB_LOG"
exit "${NPX_STUB_EXIT:-0}"
"""


class RuntimeCase(ScriptCase):
    script = "agent-runtime.sh"

    def setUp(self):
        super(RuntimeCase, self).setUp()
        # An empty HOME by default, so the laptop running the suite cannot
        # answer "chrome" for a test that never installed a native host.
        self.repo.fake_home()
        self.npx_log = os.path.join(self.repo.base, "npx_calls.log")

    # ---- running one verb ----

    def runtime(self, *args, **kwargs):
        return self.repo.run("agent-runtime.sh", *args, **kwargs)

    def kind(self, **kwargs):
        return self.assertOk(self.runtime("kind", **kwargs)).strip()

    def browser(self, **kwargs):
        return self.assertOk(self.runtime("browser", **kwargs)).strip()

    # ---- shaping the machine ----

    def as_cloud(self, extra=None):
        env = {"CLAUDE_CODE_REMOTE": "true"}
        env.update(extra or {})
        return env

    def as_plain(self):
        self.repo.no_orca()

    def no_headless_anywhere(self):
        for name in ("chromium", "chromium-browser", "google-chrome", "npx"):
            self.repo.hide_tool(name)

    def stub_npx(self, exit_code=0):
        open(self.npx_log, "w").close()
        self.repo.stub_tool("npx", NPX_STUB)
        return {"NPX_STUB_LOG": self.npx_log, "NPX_STUB_EXIT": str(exit_code)}

    def npx_calls(self):
        if not os.path.exists(self.npx_log):
            return []
        with open(self.npx_log) as fh:
            return [line.rstrip("\n").split("\t")[1:]
                    for line in fh if line.startswith("NPX")]


# ---------------------------------------------------------------- kind


class TestKindFromAgentConf(RuntimeCase):
    """agent.conf wins over everything the machine looks like."""

    def test_each_named_kind_is_obeyed(self):
        for want in KINDS:
            with self.subTest(runtime=want):
                self.repo.set_conf("runtime", want)
                self.assertEqual(self.kind(), want)

    def test_orca_is_obeyed_even_with_no_orca_on_the_machine(self):
        self.repo.set_conf("runtime", "orca")
        self.as_plain()
        self.assertEqual(self.kind(), "orca")

    def test_plain_is_obeyed_even_when_orca_answers(self):
        self.repo.set_conf("runtime", "plain")
        self.assertEqual(self.kind(), "plain")

    def test_plain_asks_orca_nothing(self):
        self.repo.set_conf("runtime", "plain")
        self.kind()
        self.assertEqual(self.repo.calls(), [])

    def test_conf_beats_the_cloud_marker(self):
        self.repo.set_conf("runtime", "orca")
        self.assertEqual(self.kind(env={"CLAUDE_CODE_REMOTE": "true"}), "orca")


class TestKindFromTheEnvironment(RuntimeCase):
    """RUNTIME_KIND is a caller's one-shot override. It wins over everything."""

    def test_each_named_kind_is_obeyed(self):
        for want in KINDS:
            with self.subTest(runtime=want):
                self.assertEqual(self.kind(env={"RUNTIME_KIND": want}), want)

    def test_it_beats_agent_conf(self):
        self.repo.set_conf("runtime", "orca")
        self.assertEqual(self.kind(env={"RUNTIME_KIND": "plain"}), "plain")

    def test_it_beats_the_cloud_marker(self):
        self.assertEqual(
            self.kind(env={"RUNTIME_KIND": "plain",
                           "CLAUDE_CODE_REMOTE": "true"}), "plain")

    def test_plain_asks_orca_nothing(self):
        self.kind(env={"RUNTIME_KIND": "plain"})
        self.assertEqual(self.repo.calls(), [])

    def test_orca_is_obeyed_with_no_orca_on_the_machine(self):
        self.as_plain()
        self.assertEqual(self.kind(env={"RUNTIME_KIND": "orca"}), "orca")

    def test_an_empty_value_is_ignored(self):
        self.repo.set_conf("runtime", "cloud")
        self.assertEqual(self.kind(env={"RUNTIME_KIND": ""}), "cloud")

    def test_an_unknown_value_is_ignored(self):
        self.repo.set_conf("runtime", "cloud")
        self.assertEqual(self.kind(env={"RUNTIME_KIND": "banana"}), "cloud")

    def test_it_saves_the_probe_for_every_later_call(self):
        """A caller that already knows the kind must not pay for it again."""
        self.repo.set_conf("runtime", "auto")
        self.assertOk(self.runtime("ps", env={"RUNTIME_KIND": "orca"}))
        self.assertEqual(self.repo.calls(), [["worktree", "ps", "--json"]])

    def test_the_script_never_sets_it_itself(self):
        """It is an override a caller passes in, never a cache we write."""
        out = self.assertOk(self.repo.run("twice_env.sh"))
        self.assertEqual(self.lines(out.strip()), ["orca", "unset"])

    def setUp(self):
        super(TestKindFromTheEnvironment, self).setUp()
        self.repo.write_bin_script("twice_env.sh", """#!/usr/bin/env bash
. "$(dirname "$0")/agent-runtime.sh"
runtime_kind
echo "${RUNTIME_KIND:-unset}"
""")


class TestKindAuto(RuntimeCase):
    def test_auto_with_orca_answering_is_orca(self):
        self.repo.set_conf("runtime", "auto")
        self.assertEqual(self.kind(), "orca")

    def test_no_runtime_line_behaves_like_auto(self):
        self.assertEqual(self.kind(), "orca")

    def test_an_unknown_value_falls_through_to_auto(self):
        self.repo.set_conf("runtime", "banana")
        self.assertEqual(self.kind(), "orca")

    def test_no_agent_conf_at_all_still_answers(self):
        os.remove(self.repo.path("agent.conf"))
        self.assertIn(self.kind(), KINDS)

    def test_no_orca_on_path_is_plain(self):
        self.as_plain()
        self.assertEqual(self.kind(), "plain")

    def test_no_orca_on_path_calls_nothing(self):
        self.as_plain()
        self.kind()
        self.assertEqual(self.repo.calls(), [])

    def test_orca_present_but_not_answering_is_plain(self):
        self.repo.stub_orca_down()
        self.assertEqual(self.kind(), "plain")

    def test_orca_slower_than_three_seconds_is_plain(self):
        self.assertEqual(self.kind(env={"ORCA_STUB_SLEEP": "6"}), "plain")

    def test_a_slow_orca_does_not_hang_the_caller(self):
        started = time.time()
        self.runtime("kind", env={"ORCA_STUB_SLEEP": "20"}, timeout=30)
        self.assertLess(time.time() - started, 10,
                        "the 3 second probe did not cut the call off")

    def test_a_fast_orca_is_not_cut_off(self):
        self.assertEqual(self.kind(env={"ORCA_STUB_SLEEP": "1"}), "orca")


class TestKindCloud(RuntimeCase):
    def test_the_remote_marker_wins_over_a_live_orca(self):
        self.assertEqual(self.kind(env={"CLAUDE_CODE_REMOTE": "true"}), "cloud")

    def test_cloud_asks_orca_nothing(self):
        self.kind(env={"CLAUDE_CODE_REMOTE": "true"})
        self.assertEqual(self.repo.calls(), [])

    def test_the_marker_set_to_false_is_not_cloud(self):
        self.assertNotEqual(self.kind(env={"CLAUDE_CODE_REMOTE": "false"}),
                            "cloud")

    def test_an_unset_marker_is_not_cloud(self):
        self.assertNotEqual(self.kind(), "cloud")

    def test_cloud_with_no_orca_is_still_cloud(self):
        self.as_plain()
        self.assertEqual(self.kind(env={"CLAUDE_CODE_REMOTE": "true"}), "cloud")


class TestKindIsNeverCached(RuntimeCase):
    """The owner switches between Orca and the Claude app inside one day."""

    def test_the_answer_changes_inside_one_shell(self):
        script = self.repo.write_bin_script("twice.sh", """#!/usr/bin/env bash
. "$(dirname "$0")/agent-runtime.sh"
runtime_kind
export CLAUDE_CODE_REMOTE=true
runtime_kind
""")
        self.assertTrue(os.path.exists(script))
        out = self.assertOk(self.repo.run("twice.sh"))
        self.assertEqual(self.lines(out.strip()), ["orca", "cloud"])

    def test_it_leaves_no_temp_file_behind(self):
        folder = os.path.join(self.repo.base, "probe_tmp")
        os.makedirs(folder)
        self.assertEqual(self.kind(env={"TMPDIR": folder}), "orca")
        self.assertEqual(os.listdir(folder), [])

    def test_a_cut_off_probe_leaves_no_temp_file_behind(self):
        folder = os.path.join(self.repo.base, "probe_tmp_slow")
        os.makedirs(folder)
        self.assertEqual(
            self.kind(env={"TMPDIR": folder, "ORCA_STUB_SLEEP": "6"}), "plain")
        self.assertEqual(os.listdir(folder), [])

    def test_it_writes_no_cache_file(self):
        def snapshot():
            out = set()
            for dirpath, _, names in os.walk(self.repo.dir):
                for name in names:
                    out.add(os.path.join(dirpath, name))
            return out

        self.kind()
        before = snapshot()
        self.as_plain()
        self.assertEqual(self.kind(), "plain")
        self.assertEqual(snapshot() - before, set())


# ---------------------------------------------------------------- ps


class TestPs(RuntimeCase):
    def setUp(self):
        super(TestPs, self).setUp()
        self.repo.set_conf("runtime", "orca")

    def test_orca_prints_the_json(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        out = self.assertOk(self.runtime("ps"))
        self.assertIn(path, out)

    def test_orca_makes_exactly_one_call(self):
        self.assertOk(self.runtime("ps"))
        self.assertEqual(self.repo.calls(), [["worktree", "ps", "--json"]])

    def test_auto_costs_one_extra_call_for_the_probe(self):
        self.repo.set_conf("runtime", "auto")
        self.assertOk(self.runtime("ps"))
        self.assertEqual(self.repo.calls(),
                         [["worktree", "ps", "--json"]] * 2)

    def test_orca_down_exits_one_with_no_output(self):
        self.repo.stub_orca_down()
        result = self.runtime("ps")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_plain_is_empty_and_ok(self):
        self.repo.set_conf("runtime", "plain")
        self.assertEqual(self.assertOk(self.runtime("ps")).strip(), "")

    def test_cloud_is_empty_and_ok(self):
        # setUp pinned the conf to orca, and the conf wins over the marker, so
        # this test has to say cloud in the conf as well as in the environment.
        self.repo.set_conf("runtime", "cloud")
        self.assertEqual(
            self.assertOk(self.runtime("ps", env=self.as_cloud())).strip(), "")

    def test_plain_calls_orca_never(self):
        self.repo.set_conf("runtime", "plain")
        self.assertOk(self.runtime("ps"))
        self.assertEqual(self.repo.calls(), [])


# ---------------------------------------------------------------- launch


class TestLaunchWithOrca(RuntimeCase):
    def setUp(self):
        super(TestLaunchWithOrca, self).setUp()
        self.repo.set_conf("runtime", "orca")

    def launch(self, **kwargs):
        return self.runtime("launch", "/tmp/wt", "TM alpha",
                            "claude --model opus", **kwargs)

    def test_the_exact_argument_list(self):
        self.assertOk(self.launch())
        self.assertEqual(
            self.repo.calls(),
            [["terminal", "create",
              "--worktree", "path:/tmp/wt",
              "--title", "TM alpha",
              "--command", "claude --model opus",
              "--json"]])

    def test_a_title_with_spaces_stays_one_argument(self):
        self.assertOk(self.launch())
        call = self.repo.calls()[0]
        self.assertIn("TM alpha", call)


class TestLaunchWithoutTerminals(RuntimeCase):
    """plain and cloud cannot open a terminal, and must say so."""

    def launch(self, **kwargs):
        return self.runtime("launch", "/tmp/wt", "TM alpha", "claude", **kwargs)

    def each_mode(self):
        yield "plain", {"conf": "plain"}
        yield "cloud", {"env": self.as_cloud()}

    def run_mode(self, setup):
        if "conf" in setup:
            self.repo.set_conf("runtime", setup["conf"])
            return self.launch()
        return self.launch(env=setup["env"])

    def test_it_fails(self):
        for name, setup in self.each_mode():
            with self.subTest(kind=name):
                self.repo.clear_calls()
                result = self.run_mode(setup)
                self.assertNotEqual(result.returncode, 0,
                                    "a launch that cannot happen must not "
                                    "report success")

    def test_it_says_to_use_the_agent_tool(self):
        for name, setup in self.each_mode():
            with self.subTest(kind=name):
                self.repo.clear_calls()
                result = self.run_mode(setup)
                self.assertIn("Agent", result.stderr)

    def test_the_message_is_one_line_on_stderr(self):
        for name, setup in self.each_mode():
            with self.subTest(kind=name):
                self.repo.clear_calls()
                result = self.run_mode(setup)
                self.assertEqual(len(result.stderr.strip().splitlines()), 1,
                                 result.stderr)

    def test_it_prints_nothing_on_stdout(self):
        for name, setup in self.each_mode():
            with self.subTest(kind=name):
                self.repo.clear_calls()
                result = self.run_mode(setup)
                self.assertEqual(result.stdout.strip(), "")

    def test_it_calls_orca_never(self):
        for name, setup in self.each_mode():
            with self.subTest(kind=name):
                self.repo.clear_calls()
                self.run_mode(setup)
                self.assertEqual(self.repo.calls(), [])


# ---------------------------------------------------------------- close


class TestClose(RuntimeCase):
    def test_orca_closes_the_terminal(self):
        self.repo.set_conf("runtime", "orca")
        self.assertOk(self.runtime("close", "term_123"))
        self.assertEqual(
            self.repo.calls(),
            [["terminal", "close", "--terminal", "term_123", "--json"]])

    def test_plain_is_a_quiet_success(self):
        self.repo.set_conf("runtime", "plain")
        result = self.runtime("close", "term_123")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(self.repo.calls(), [])

    def test_cloud_is_a_quiet_success(self):
        result = self.runtime("close", "term_123", env=self.as_cloud())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.repo.calls(), [])


# ---------------------------------------------------------------- browser


class TestBrowserOnALocalMachine(RuntimeCase):
    """orca and plain both reach Claude in Chrome. Orca is irrelevant to it."""

    def test_every_native_host_location_counts(self):
        for browser in ("chrome", "edge", "chrome-linux", "edge-linux"):
            with self.subTest(browser=browser):
                repo = self.repo
                repo.fake_home()
                path = repo.install_native_host(browser)
                self.assertEqual(self.browser(), "chrome")
                os.remove(path)

    def test_an_empty_home_is_none(self):
        self.assertEqual(self.browser(), "none")

    def test_plain_with_the_extension_is_chrome(self):
        self.repo.set_conf("runtime", "plain")
        self.repo.install_native_host("chrome")
        self.assertEqual(self.browser(), "chrome")

    def test_plain_without_the_extension_is_none(self):
        self.repo.set_conf("runtime", "plain")
        self.assertEqual(self.browser(), "none")

    def test_orca_without_the_extension_is_none(self):
        self.repo.set_conf("runtime", "orca")
        self.assertEqual(self.browser(), "none")


class TestBrowserInTheCloud(RuntimeCase):
    """Claude in Chrome can never reach a VM. Headless is the real option."""

    def test_a_chromium_binary_makes_it_headless(self):
        for name in ("chromium", "chromium-browser", "google-chrome"):
            with self.subTest(binary=name):
                self.no_headless_anywhere()
                self.repo.stub_tool(name)
                self.assertEqual(self.browser(env=self.as_cloud()), "headless")

    def test_playwright_alone_makes_it_headless(self):
        self.no_headless_anywhere()
        env = self.as_cloud(self.stub_npx(exit_code=0))
        self.assertEqual(self.browser(env=env), "headless")

    def test_the_playwright_probe_never_downloads(self):
        self.no_headless_anywhere()
        env = self.as_cloud(self.stub_npx(exit_code=0))
        self.browser(env=env)
        self.assertTrue(self.npx_calls(), "npx was never asked")
        for call in self.npx_calls():
            self.assertIn("--no-install", call)

    def test_a_failing_playwright_probe_is_none(self):
        self.no_headless_anywhere()
        env = self.as_cloud(self.stub_npx(exit_code=1))
        self.assertEqual(self.browser(env=env), "none")

    def test_nothing_installed_is_none(self):
        self.no_headless_anywhere()
        self.assertEqual(self.browser(env=self.as_cloud()), "none")

    def test_the_native_host_file_never_makes_the_cloud_say_chrome(self):
        self.no_headless_anywhere()
        self.repo.install_native_host("chrome-linux")
        self.assertEqual(self.browser(env=self.as_cloud()), "none")


# ---------------------------------------------------------------- shape


class TestItCanBeSourced(RuntimeCase):
    def test_sourcing_defines_every_function(self):
        self.repo.write_bin_script("probe.sh", """#!/usr/bin/env bash
. "$(dirname "$0")/agent-runtime.sh"
for fn in %s; do
  if declare -F "$fn" >/dev/null; then echo "have $fn"; else echo "missing $fn"; fi
done
""" % " ".join(FUNCTIONS))
        out = self.assertOk(self.repo.run("probe.sh"))
        for name in FUNCTIONS:
            with self.subTest(function=name):
                self.assertIn("have %s" % name, out)

    def test_sourcing_runs_nothing(self):
        self.repo.write_bin_script("quiet.sh", """#!/usr/bin/env bash
. "$(dirname "$0")/agent-runtime.sh"
echo DONE
""")
        out = self.assertOk(self.repo.run("quiet.sh"))
        self.assertEqual(self.lines(out.strip()), ["DONE"])
        self.assertEqual(self.repo.calls(), [])


class TestUsage(RuntimeCase):
    def test_it_is_executable(self):
        full = os.path.join(os.path.dirname(HERE), "bin", "agent-runtime.sh")
        self.assertTrue(os.access(full, os.X_OK))

    def test_help_exits_zero_and_names_itself(self):
        result = self.runtime("-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent-runtime.sh", result.stdout)

    def test_help_lists_every_verb(self):
        out = self.assertOk(self.runtime("-h"))
        for verb in ("kind", "ps", "browser", "launch", "close"):
            with self.subTest(verb=verb):
                self.assertIn(verb, out)

    def test_no_argument_exits_two(self):
        self.assertEqual(self.runtime().returncode, 2)

    def test_an_unknown_verb_exits_two(self):
        self.assertEqual(self.runtime("teleport").returncode, 2)

    def test_it_runs_from_any_directory(self):
        self.assertIn(self.kind(cwd=self.repo.plugin), KINDS)


if __name__ == "__main__":
    unittest.main()
