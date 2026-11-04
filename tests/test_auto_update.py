"""Failing tests for auto-update (owner, 2026-11-04: "config during setup,
default is auto update, if the user close the auto update also can").
Written by the task manager, before any code.

FACTS (Claude Code 2.1.318, read in its code): the /plugin "Enable
auto-update" toggle of a marketplace writes autoUpdate=<bool> on that
marketplace's entry in <claude dir>/plugins/known_marketplaces.json AND on
its extraKnownMarketplaces entry in the settings file that declares it (the
user settings.json after `claude plugin marketplace add`). At startup Claude
Code copies a declared settings autoUpdate into known_marketplaces.json.
<claude dir> = $CLAUDE_CONFIG_DIR when set and not empty, else ~/.claude.

CONTRACT

1. auto_update=on|off lives in the user file of personal-mode
   (agent_conf.USER_KEYS, read_user_conf, effective; never agent.conf:
   `agent-settings.sh auto_update on` is refused as an unknown key).
   Not set -> on (`agent-settings.sh get auto_update` -> "on (default)").

2. bin/agent_update.py (new), stdlib only, never raises, never a traceback.
   MARKETPLACE = "auto-pipeline"
   claude_dir(env=None) -> ENV (default os.environ) CLAUDE_CONFIG_DIR when
     not empty, else ~/.claude ($HOME at call time).
   apply_auto_update(on, cdir) -> list of str (one line per file looked at)
     For <cdir>/settings.json entry ["extraKnownMarketplaces"]["auto-pipeline"]
     and <cdir>/plugins/known_marketplaces.json entry ["auto-pipeline"]: when
     the file is a JSON object and the entry is a dict, and entry autoUpdate
     is not already ON (a JSON bool): first copy the file byte for byte to
     "<file>.bak-auto-pipeline", then write it back with only
     entry["autoUpdate"] = ON changed (key order kept, indent 2). Already ON:
     nothing written, no backup. No file, broken JSON, no entry: untouched.
     Never creates a file, never touches any other file (a repo's
     .claude/settings.json above all).
   CLI `agent_update.py apply on|off`: claude_dir() of the environment, the
     lines on stdout, exit 0; any other argument -> exit 2.
   parse_version(s) -> tuple of ints ("0.29.0" -> (0, 29, 0)), None when not
     dotted digits. Compare numeric: 0.10.0 > 0.9.0.
   installed_version(plugin_root) -> "version" of
     <plugin_root>/.claude-plugin/plugin.json, or None.
   clone_version(cdir) -> (version, subject) of the marketplace clone
     <cdir>/plugins/marketplaces/auto-pipeline: "version" of its
     .claude-plugin/plugin.json (None when missing), and subject = the
     subject of the last commit there that touched .claude-plugin/plugin.json
     (the release commit; None when not a git repo).
   cache_path() -> agent_conf.user_conf_path() + ".latest.json"
   version_url(cdir, env=None) -> ENV AUTO_PIPELINE_VERSION_URL when not
     empty; else, when known_marketplaces.json's auto-pipeline source is
     {"source": "github", "repo": "<o>/<r>"},
     "https://raw.githubusercontent.com/<o>/<r>/HEAD/.claude-plugin/plugin.json";
     else None.
   refresh(url, cache, timeout=4, now=None) -> fetches URL (urllib, file://
     works too), takes "version" of the JSON; writes CACHE as JSON
     {"checked": <now, epoch s>, "version": <v or null>}. Any failure (offline,
     timeout, junk) -> {"checked": now, "version": null}. Silent.
   stale(cache, now=None) -> True when CACHE is missing, broken or "checked"
     is 86400 s or more before NOW.
   notice_line(plugin_root, cdir, cache) -> str or None.
     newest = the higher of clone_version and the cache's version. Installed
     unknown, newest unknown, or installed >= newest -> None. Else:
     "UPDATE: auto-pipeline <new> available (you run <old>): <subject>. Auto
     update on: installs by itself within 10 min, then /reload-plugins. Off:
     claude plugin update auto-pipeline@auto-pipeline"
     <subject> only when the clone holds <new> and has a subject, cut to 80
     characters (77 + "..."); without it the "(you run <old>)" is followed
     straight by ". Auto update on: ...".
   CLI `agent_update.py notice <plugin_root>`: prints the line when there is
     one. When stale(cache_path()) and version_url() is not None it starts
     `agent_update.py refresh` detached (new session, stdio to /dev/null) and
     never waits for it. Exit 0 always, well under a second.
   CLI `agent_update.py refresh`: refresh(version_url(), cache_path()) when
     the url is not None. Exit 0 always.

3. bin/agent-settings.sh --user auto_update on|off saves the user file
   (personal-mode) and then applies it: runs `agent_update.py apply <v>`,
   its lines on stdout.

4. bin/agent-init.sh [--auto-update on|off]
   --auto-update on|off -> `agent-settings.sh --user auto_update <v>` (its
     "saved: auto_update=<v>" line shows), always, set or not. Any other
     value or none -> exit 2, a message on stderr, nothing created.
   No flag, auto_update already in the user file -> no question, unchanged.
   No flag, not set, stdin a terminal -> ONE question on stderr, starting
     "Auto update:", on first and marked recommended, then off. Answer on /
     off, any case; Enter, EOF or anything else -> on. Asked after the
     permission question.
   No flag, not set, stdin not a terminal -> on, saved, no question.
   skills/init/SKILL.md: one question auto update, "on (Recommended)" then
     "off" -> --auto-update on|off.

5. Start text (bin/agent-start.sh), main manager (main, takeover) and
   human-direct only, never a spawned agent, not on the compact path:
   auto_update not in the user file -> exactly one line starting
     "AUTO UPDATE: not set." that says ask the human once, on (recommended)
     or off, and holds the command
     "<plugin>/bin/agent-settings.sh --user auto_update on|off".
   Set -> no such line.
   `agent_update.py notice <plugin root>` -> its UPDATE line when it prints
     one. The start never waits on the network.

6. skills/merge/SKILL.md: every release bumps the version in
   .claude-plugin/plugin.json; users get nothing without it.
"""

import json
import os
import pty
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_conf  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402

TAIL = (". Auto update on: installs by itself within 10 min, then /reload-plugins. "
        "Off: claude plugin update auto-pipeline@auto-pipeline")


def update_mod():
    import agent_update
    return agent_update


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def write_json(path, data, raw=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(raw if raw is not None else json.dumps(data, indent=2))
    return path


def git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


SETTINGS = {
    "model": "opus",
    "extraKnownMarketplaces": {
        "other": {"source": {"source": "github", "repo": "x/other"}},
        "auto-pipeline": {"source": {"source": "github", "repo": "maverick1014/auto-pipeline"}},
    },
    "enabledPlugins": {"auto-pipeline@auto-pipeline": True},
}
KNOWN = {
    "claude-plugins-official": {"source": {"source": "github", "repo": "anthropics/claude-plugins-official"},
                                "installLocation": "/x/official", "lastUpdated": "2026-11-04T07:04:39.737Z"},
    "auto-pipeline": {"source": {"source": "github", "repo": "maverick1014/auto-pipeline"},
                      "installLocation": "/x/auto-pipeline", "lastUpdated": "2026-11-04T01:32:15.992Z"},
}


class Tmp(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="auto_update_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.cdir = os.path.join(self.base, "home", ".claude")
        os.makedirs(self.cdir)
        self.user = os.path.join(self.base, "u", "auto-pipeline.conf")
        p = mock.patch.dict(os.environ, {"AUTO_PIPELINE_USER_CONF": self.user,
                                         "HOME": os.path.join(self.base, "home")})
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        os.environ.pop("AUTO_PIPELINE_VERSION_URL", None)

    def settings_path(self):
        return os.path.join(self.cdir, "settings.json")

    def known_path(self):
        return os.path.join(self.cdir, "plugins", "known_marketplaces.json")

    def load(self, path):
        with open(path) as fh:
            return json.load(fh)


# ------------------------------------------------------------- 1: the key

class TestKey(Tmp):
    def test_a_user_key_not_an_agent_conf_key(self):
        self.assertIn("auto_update", agent_conf.USER_KEYS)
        template = agent_conf.load(os.path.join(BIN, "agent.conf.default"))
        self.assertNotIn("auto_update", template)
        self.assertNotIn("auto_update", agent_conf.load(os.path.join(ROOT, "agent.conf")))


# ------------------------------------------------------- 2: apply (native)

class TestApply(Tmp):
    def test_claude_dir(self):
        u = update_mod()
        self.assertEqual(u.MARKETPLACE, "auto-pipeline")
        self.assertEqual(u.claude_dir(), self.cdir)
        self.assertEqual(u.claude_dir({"CLAUDE_CONFIG_DIR": "/cfg", "HOME": "/h"}), "/cfg")
        self.assertEqual(u.claude_dir({"CLAUDE_CONFIG_DIR": "", "HOME": "/h"}), "/h/.claude")

    def test_both_files_get_it_and_nothing_else_changes(self):
        u = update_mod()
        s = write_json(self.settings_path(), SETTINGS)
        k = write_json(self.known_path(), KNOWN)
        s_before, k_before = open(s).read(), open(k).read()
        lines = u.apply_auto_update(False, self.cdir)
        self.assertIsInstance(lines, list)
        self.assertEqual(open(s + ".bak-auto-pipeline").read(), s_before)
        self.assertEqual(open(k + ".bak-auto-pipeline").read(), k_before)
        want_s = json.loads(json.dumps(SETTINGS))
        want_s["extraKnownMarketplaces"]["auto-pipeline"]["autoUpdate"] = False
        want_k = json.loads(json.dumps(KNOWN))
        want_k["auto-pipeline"]["autoUpdate"] = False
        self.assertEqual(self.load(s), want_s)
        self.assertEqual(self.load(k), want_k)
        self.assertEqual(list(self.load(s)), list(SETTINGS), "key order kept")
        self.assertEqual(list(self.load(k)), list(KNOWN))
        u.apply_auto_update(True, self.cdir)
        self.assertIs(self.load(s)["extraKnownMarketplaces"]["auto-pipeline"]["autoUpdate"], True)
        self.assertIs(self.load(k)["auto-pipeline"]["autoUpdate"], True)
        self.assertNotIn("autoUpdate", self.load(s)["extraKnownMarketplaces"]["other"])
        self.assertNotIn("autoUpdate", self.load(k)["claude-plugins-official"])

    def test_already_set_writes_nothing(self):
        u = update_mod()
        data = json.loads(json.dumps(KNOWN))
        data["auto-pipeline"]["autoUpdate"] = True
        k = write_json(self.known_path(), data, raw=json.dumps(data))
        before = os.stat(k).st_mtime_ns, open(k).read()
        time.sleep(0.01)
        u.apply_auto_update(True, self.cdir)
        self.assertEqual((os.stat(k).st_mtime_ns, open(k).read()), before)
        self.assertFalse(os.path.exists(k + ".bak-auto-pipeline"))

    def test_no_entry_or_broken_or_missing_is_untouched(self):
        u = update_mod()
        s = write_json(self.settings_path(), {"model": "opus"})
        k = write_json(self.known_path(), None, raw="{broken")
        u.apply_auto_update(False, self.cdir)
        self.assertEqual(self.load(s), {"model": "opus"})
        self.assertEqual(open(k).read(), "{broken")
        self.assertFalse(os.path.exists(s + ".bak-auto-pipeline"))
        self.assertFalse(os.path.exists(k + ".bak-auto-pipeline"))
        empty = os.path.join(self.base, "empty", ".claude")
        self.assertIsInstance(u.apply_auto_update(True, empty), list)
        self.assertFalse(os.path.exists(empty), "never creates a file or folder")

    def test_cli(self):
        write_json(self.known_path(), KNOWN)
        repo_settings = write_json(os.path.join(self.base, "repo", ".claude", "settings.json"), SETTINGS)
        before = open(repo_settings).read()
        r = subprocess.run([sys.executable, os.path.join(BIN, "agent_update.py"), "apply", "off"],
                           capture_output=True, text=True, env=dict(os.environ), timeout=30,
                           cwd=os.path.join(self.base, "repo"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(self.load(self.known_path())["auto-pipeline"]["autoUpdate"], False)
        self.assertEqual(open(repo_settings).read(), before, "a repo's .claude/settings.json is never touched")
        for bad in ([], ["maybe"], ["on", "off"]):
            with self.subTest(args=bad):
                r = subprocess.run([sys.executable, os.path.join(BIN, "agent_update.py"), "apply"] + bad,
                                   capture_output=True, text=True, env=dict(os.environ), timeout=30)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn("Traceback", r.stderr)


# ---------------------------------------------------- 2: versions, notice

class TestVersions(Tmp):
    def plugin(self, version):
        root = os.path.join(self.base, "plugin")
        write_json(os.path.join(root, ".claude-plugin", "plugin.json"), {"name": "auto-pipeline", "version": version})
        return root

    def clone(self, version, subject="release %s: something new"):
        root = os.path.join(self.cdir, "plugins", "marketplaces", "auto-pipeline")
        os.makedirs(root, exist_ok=True)
        if not os.path.isdir(os.path.join(root, ".git")):
            git(root, "init", "-q")
        write_json(os.path.join(root, ".claude-plugin", "plugin.json"), {"name": "auto-pipeline", "version": version})
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", subject % version if "%s" in subject else subject)
        with open(os.path.join(root, "other.txt"), "a") as fh:
            fh.write("x\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "a later commit that is not the release")
        return root

    def cache(self, version, checked=None):
        u = update_mod()
        write_json(u.cache_path(), {"checked": checked if checked is not None else time.time(), "version": version})
        return u.cache_path()

    def test_parse_version(self):
        u = update_mod()
        self.assertEqual(u.parse_version("0.29.0"), (0, 29, 0))
        self.assertEqual(u.parse_version("1.2"), (1, 2))
        self.assertGreater(u.parse_version("0.10.0"), u.parse_version("0.9.0"))
        for bad in (None, "", "v1.2", "1.x", "abc"):
            with self.subTest(bad=bad):
                self.assertIsNone(u.parse_version(bad))

    def test_installed_and_clone(self):
        u = update_mod()
        self.assertEqual(u.installed_version(self.plugin("0.29.0")), "0.29.0")
        self.assertIsNone(u.installed_version(os.path.join(self.base, "nowhere")))
        self.assertEqual(u.clone_version(self.cdir), (None, None))
        self.clone("0.30.0")
        self.assertEqual(u.clone_version(self.cdir), ("0.30.0", "release 0.30.0: something new"))

    def test_cache_path_sits_next_to_the_user_file(self):
        self.assertEqual(update_mod().cache_path(), self.user + ".latest.json")

    def test_version_url(self):
        u = update_mod()
        self.assertIsNone(u.version_url(self.cdir, {}))
        write_json(self.known_path(), KNOWN)
        self.assertEqual(u.version_url(self.cdir, {}),
                         "https://raw.githubusercontent.com/maverick1014/auto-pipeline/HEAD/.claude-plugin/plugin.json")
        self.assertEqual(u.version_url(self.cdir, {"AUTO_PIPELINE_VERSION_URL": "file:///x"}), "file:///x")
        write_json(self.known_path(), {"auto-pipeline": {"source": {"source": "directory", "path": "/p"}}})
        self.assertIsNone(u.version_url(self.cdir, {}))

    def test_refresh_and_stale(self):
        u = update_mod()
        remote = write_json(os.path.join(self.base, "remote", "plugin.json"), {"version": "0.31.0"})
        cache = os.path.join(self.base, "c.json")
        self.assertTrue(u.stale(cache))
        u.refresh("file://" + remote, cache, now=1000)
        self.assertEqual(self.load(cache), {"checked": 1000, "version": "0.31.0"})
        self.assertFalse(u.stale(cache, now=1000 + 86399))
        self.assertTrue(u.stale(cache, now=1000 + 86400))
        u.refresh("file://" + os.path.join(self.base, "nope.json"), cache, now=2000)
        self.assertEqual(self.load(cache), {"checked": 2000, "version": None})
        u.refresh("http://127.0.0.1:9/plugin.json", cache, timeout=1, now=3000)
        self.assertEqual(self.load(cache), {"checked": 3000, "version": None})
        with open(cache, "w") as fh:
            fh.write("junk")
        self.assertTrue(u.stale(cache))

    def test_notice_from_the_clone(self):
        u = update_mod()
        self.clone("0.30.0")
        line = u.notice_line(self.plugin("0.29.0"), self.cdir, u.cache_path())
        self.assertEqual(line, "UPDATE: auto-pipeline 0.30.0 available (you run 0.29.0): "
                               "release 0.30.0: something new" + TAIL)

    def test_notice_from_the_cache_has_no_subject(self):
        u = update_mod()
        self.clone("0.30.0")
        self.cache("0.31.0")
        line = u.notice_line(self.plugin("0.29.0"), self.cdir, u.cache_path())
        self.assertEqual(line, "UPDATE: auto-pipeline 0.31.0 available (you run 0.29.0)" + TAIL)

    def test_numeric_compare(self):
        u = update_mod()
        self.cache("0.10.0")
        self.assertIsNotNone(u.notice_line(self.plugin("0.9.0"), self.cdir, u.cache_path()))
        self.assertIsNone(u.notice_line(self.plugin("0.10.0"), self.cdir, u.cache_path()))
        self.assertIsNone(u.notice_line(self.plugin("0.11.0"), self.cdir, u.cache_path()))

    def test_the_subject_is_cut(self):
        u = update_mod()
        self.clone("0.30.0", subject="release 0.30.0: " + "x" * 200)
        line = u.notice_line(self.plugin("0.29.0"), self.cdir, u.cache_path())
        subject = line.split("(you run 0.29.0): ", 1)[1][:-len(TAIL)]
        self.assertEqual(len(subject), 80)
        self.assertTrue(subject.endswith("..."))

    def test_nothing_known(self):
        u = update_mod()
        self.assertIsNone(u.notice_line(self.plugin("0.29.0"), self.cdir, u.cache_path()))
        self.cache(None)
        self.assertIsNone(u.notice_line(self.plugin("0.29.0"), self.cdir, u.cache_path()))
        self.assertIsNone(u.notice_line(os.path.join(self.base, "nowhere"), self.cdir, u.cache_path()))

    def cli(self, *args, env=None):
        e = dict(os.environ)
        e.update(env or {})
        t = time.time()
        r = subprocess.run([sys.executable, os.path.join(BIN, "agent_update.py")] + list(args),
                           capture_output=True, text=True, env=e, timeout=30)
        return r, time.time() - t

    def test_notice_cli_starts_a_refresh_and_never_waits(self):
        u = update_mod()
        remote = write_json(os.path.join(self.base, "remote", "plugin.json"), {"version": "0.32.0"})
        r, took = self.cli("notice", self.plugin("0.29.0"), env={"AUTO_PIPELINE_VERSION_URL": "file://" + remote})
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        self.assertLess(took, 2.0)
        for _ in range(100):
            if os.path.exists(u.cache_path()) and self.load(u.cache_path()).get("version"):
                break
            time.sleep(0.05)
        self.assertEqual(self.load(u.cache_path())["version"], "0.32.0", "the detached refresh wrote the cache")
        r, _ = self.cli("notice", self.plugin("0.29.0"), env={"AUTO_PIPELINE_VERSION_URL": "file://" + remote})
        self.assertEqual(r.stdout, "UPDATE: auto-pipeline 0.32.0 available (you run 0.29.0)" + TAIL + "\n")

    def test_notice_cli_with_a_hanging_network(self):
        import socket
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self.addCleanup(srv.close)
        url = "http://127.0.0.1:%d/plugin.json" % srv.getsockname()[1]
        r, took = self.cli("notice", self.plugin("0.29.0"), env={"AUTO_PIPELINE_VERSION_URL": url})
        self.assertEqual(r.returncode, 0)
        self.assertLess(took, 2.0, "the start never waits on the network")
        self.assertNotIn("Traceback", r.stderr)

    def test_fresh_cache_no_refresh(self):
        u = update_mod()
        self.cache("0.29.0", checked=time.time())
        remote = write_json(os.path.join(self.base, "remote", "plugin.json"), {"version": "0.40.0"})
        self.cli("notice", self.plugin("0.29.0"), env={"AUTO_PIPELINE_VERSION_URL": "file://" + remote})
        time.sleep(0.5)
        self.assertEqual(self.load(u.cache_path())["version"], "0.29.0", "checked less than a day ago")

    def test_refresh_cli(self):
        u = update_mod()
        remote = write_json(os.path.join(self.base, "remote", "plugin.json"), {"version": "0.33.0"})
        r, _ = self.cli("refresh", env={"AUTO_PIPELINE_VERSION_URL": "file://" + remote})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.load(u.cache_path())["version"], "0.33.0")


# ---------------------------------------------- 3: agent-settings --user

class TestSettingsApply(ScriptCase):
    script = "agent-settings.sh"

    def test_off_then_on(self):
        home = self.repo.fake_home()
        s = write_json(os.path.join(home, ".claude", "settings.json"), SETTINGS)
        k = write_json(os.path.join(home, ".claude", "plugins", "known_marketplaces.json"), KNOWN)
        out = self.assertOk(self.repo.run("agent-settings.sh", "--user", "auto_update", "off"))
        self.assertIn("saved: auto_update=off", out)
        self.assertIs(json.load(open(s))["extraKnownMarketplaces"]["auto-pipeline"]["autoUpdate"], False)
        self.assertIs(json.load(open(k))["auto-pipeline"]["autoUpdate"], False)
        self.assertEqual(agent_conf.load(self.repo.user_conf), {"auto_update": "off"})
        self.assertOk(self.repo.run("agent-settings.sh", "--user", "auto_update", "on"))
        self.assertIs(json.load(open(k))["auto-pipeline"]["autoUpdate"], True)
        self.assertEqual(self.assertOk(self.repo.run("agent-settings.sh", "get", "auto_update")),
                         "on (from %s)\n" % self.repo.user_conf)

    def test_never_in_agent_conf(self):
        r = self.repo.run("agent-settings.sh", "auto_update", "on")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("auto_update", open(self.repo.path("agent.conf")).read())

    def test_a_bad_value(self):
        r = self.repo.run("agent-settings.sh", "--user", "auto_update", "maybe")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(self.repo.user_conf))


# ----------------------------------------------------------- 4: init

class TestInit(ScriptCase):
    script = "agent-init.sh"

    def setUp(self):
        super().setUp()
        os.remove(self.repo.path("agent.conf"))
        self.repo.git_init(self.repo.dir)
        self.repo.fake_home()

    def init(self, *args):
        return self.repo.run("agent-init.sh", *args)

    def user(self):
        if not os.path.exists(self.repo.user_conf):
            return {}
        return agent_conf.load(self.repo.user_conf)

    def tty(self, answer, *args):
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([self.repo.script_path("agent-init.sh")] + list(args), cwd=self.repo.dir,
                                    env=self.repo._env(None), stdin=slave, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            os.close(slave)
            slave = None
            if answer is not None:
                os.write(master, answer.encode())
            out, err = proc.communicate(timeout=60)
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)
        return proc.returncode, out, err

    def test_flag(self):
        for value in ("off", "on"):
            with self.subTest(value=value):
                out = self.assertOk(self.init("--auto-update", value))
                self.assertIn("saved: auto_update=%s" % value, out)
                self.assertEqual(self.user()["auto_update"], value)

    def test_bad_flag(self):
        for args in (("--auto-update",), ("--auto-update", "yes"), ("--auto-update", "")):
            with self.subTest(args=args):
                r = self.init(*args)
                self.assertEqual(r.returncode, 2)
                self.assertTrue(r.stderr.strip())
                self.assertFalse(os.path.exists(self.repo.path("agent.conf")))
                self.assertFalse(os.path.exists(self.repo.user_conf))

    def test_no_terminal_is_on(self):
        r = self.init()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.user()["auto_update"], "on")
        self.assertNotIn("Auto update:", r.stdout + r.stderr)

    def test_already_set_is_kept(self):
        self.repo.set_user_conf("auto_update=off\n")
        code, out, err = self.tty("on\n")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.user()["auto_update"], "off")
        self.assertNotIn("Auto update:", err)

    def test_the_question(self):
        for answer, want in (("auto\noff\n", "off"), ("auto\nOFF\n", "off"), ("auto\non\n", "on"),
                             ("auto\n\n", "on"), ("auto\nmaybe\n", "on")):
            with self.subTest(answer=answer):
                if os.path.exists(self.repo.user_conf):
                    os.remove(self.repo.user_conf)
                if os.path.exists(self.repo.path("agent.conf")):
                    os.remove(self.repo.path("agent.conf"))
                code, out, err = self.tty(answer)
                self.assertEqual(code, 0, err)
                self.assertEqual(self.user().get("auto_update"), want)
                q = [l for l in err.splitlines() if "Auto update:" in l]
                self.assertTrue(q, err)
                self.assertLess(err.index("Permission mode for every agent:"), err.index("Auto update:"))
                tail = err[err.index("Auto update:"):]
                self.assertIn("recommended", tail.split("off")[0].lower())
                self.assertEqual(agent_conf.load(self.repo.path("agent.conf"))["permission_mode"], "auto")

    def test_the_init_skill_asks(self):
        text = read("skills", "init", "SKILL.md")
        self.assertIn("on (Recommended)", text)
        self.assertIn("--auto-update on", text)
        self.assertIn("--auto-update off", text)


# ------------------------------------------------------- 5: start text

class TestStart(ScriptCase):
    script = "agent-start.sh"

    def start(self, env=None):
        return self.assertOk(self.repo.run("agent-start.sh", env=env))

    def lines(self, out, prefix):
        return [l for l in out.splitlines() if l.startswith(prefix)]

    def test_not_set_main_manager_is_told_once(self):
        lines = self.lines(self.start(), "AUTO UPDATE:")
        self.assertEqual(len(lines), 1, lines)
        line = lines[0]
        self.assertTrue(line.startswith("AUTO UPDATE: not set."))
        self.assertIn("%s/bin/agent-settings.sh --user auto_update on|off" % self.repo.plugin, line)
        self.assertIn("once", line)
        self.assertIn("recommended", line.lower())

    def test_set_no_line(self):
        self.repo.set_user_conf("auto_update=off\n")
        self.assertEqual(self.lines(self.start(), "AUTO UPDATE:"), [])

    def test_a_spawned_agent_is_never_told(self):
        self.assertEqual(self.lines(self.start({"AGENT_ROLE": "task-manager"}), "AUTO UPDATE:"), [])

    def plugin_version(self, version):
        write_json(os.path.join(self.repo.plugin, ".claude-plugin", "plugin.json"),
                   {"name": "auto-pipeline", "version": version})

    def test_update_line(self):
        home = self.repo.fake_home()
        self.plugin_version("0.29.0")
        write_json(self.repo.user_conf + ".latest.json", {"checked": time.time(), "version": "0.30.0"})
        out = self.start()
        self.assertEqual(self.lines(out, "UPDATE:"),
                         ["UPDATE: auto-pipeline 0.30.0 available (you run 0.29.0)" + TAIL])
        self.assertTrue(home)

    def test_no_update_line_when_current(self):
        self.repo.fake_home()
        self.plugin_version("0.30.0")
        write_json(self.repo.user_conf + ".latest.json", {"checked": time.time(), "version": "0.30.0"})
        self.assertEqual(self.lines(self.start(), "UPDATE:"), [])

    def test_never_waits_on_the_network(self):
        import socket
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self.addCleanup(srv.close)
        self.repo.fake_home()
        self.plugin_version("0.29.0")
        t = time.time()
        self.start({"AUTO_PIPELINE_VERSION_URL": "http://127.0.0.1:%d/p.json" % srv.getsockname()[1],
                    "AGENT_ROLE": "task-manager"})
        self.start({"AUTO_PIPELINE_VERSION_URL": "http://127.0.0.1:%d/p.json" % srv.getsockname()[1]})
        self.assertLess(time.time() - t, 20)


class TestReleaseText(unittest.TestCase):
    def test_merge_skill_says_bump_the_version(self):
        text = read("skills", "merge", "SKILL.md")
        line = next((l for l in text.splitlines() if ".claude-plugin/plugin.json" in l), None)
        self.assertIsNotNone(line)
        self.assertIn("version", line)
        self.assertIn("release", line.lower())


if __name__ == "__main__":
    unittest.main()
