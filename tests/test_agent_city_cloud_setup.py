"""Failing tests, cloud-city-1 slice 5: the setup steps a person follows by
hand and the deploy folder (requirements/city.md, "Cloud page" and "Relay setup").

Logins, keys and the deploy are the owner's: agents never type, print or
store a key or a token, and never run a login or the deploy.

  ./agent-city.sh cloud-build <dir> --d1-id <id> [--d1-name <name>] [--name <worker name>]
      Makes the folder wrangler deploys from. No network, no wrangler, no login.
        <dir>/worker.js            a copy of bin/agent-city-cloud.js
        <dir>/site/index.html      a copy of bin/agent-city.html, byte for byte
                                   (the Worker fills the placeholders)
        <dir>/site/assets/...      a copy of bin/agent-city-assets
        <dir>/wrangler.jsonc       plain JSON (no comments):
          {"name": "<worker name, default agent-city-page>",
           "main": "worker.js",
           "compatibility_date": "<a date, YYYY-MM-DD>",
           "keep_vars": true,                (the values typed in the dashboard stay)
           "workers_dev": true,
           "assets": {"directory": "./site", "binding": "ASSETS", "run_worker_first": true},
           "d1_databases": [{"binding": "DB", "database_name": "<name, default agent-city>",
                             "database_id": "<id>"}],
           "vars": {"CITY_LANG": "<language of agent.conf>", "CITY_ASSET_V": "<not empty>"}}
      --d1-id: the D1 database the relay uses (a UUID, not a secret). Missing
      or not a UUID -> exit 2, nothing is written. Run again on the same
      folder: it is made anew (old asset files do not stay).
      stdout: "CLOUD: built <dir>" then
              "CLOUD: deploy it yourself: cd <dir> && npx wrangler deploy"
      It never has an Access value, a key or an e-mail in any file.

  ./agent-city.sh cloud-deploy
      For the owner, in his own terminal only: asks the D1 database id, builds
      into <AGENT_CITY_HOME>/cloud-site and runs `npx wrangler deploy` there.
      Without a terminal on stdin (an agent, a pipe) it refuses: exit 2,
      "CLOUD: run this yourself in your own terminal ..." and nothing runs.

  skills/city/setup.md   new sections after "Remove the relay", same style
      (numbered steps, plain words, each section ends with "You should see"):
      turn the cloud page on (new relay code, CITY_USER), deploy the page
      (npx wrangler login, cloud-deploy), the login (Enable Cloudflare Access,
      one-time code, ACCESS_TEAM and ACCESS_AUD), check it works (CLOUD: on,
      open the address on a phone), turn it off. It says what the free plan
      allows and that a machine needs nothing typed (the city starts itself).

Run: python3 -m unittest tests.test_agent_city_cloud_setup
"""

import json
import os
import re
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase  # noqa: E402

D1 = "0a1b2c3d-1111-4222-8333-444455556666"
SETUP = os.path.join(ROOT, "skills", "city", "setup.md")
REQ = os.path.join(ROOT, "requirements", "city.md")


class BuildCase(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.assertTrue(os.path.exists(os.path.join(self.repo.plugin_bin, "agent-city-cloud.js")),
                        "bin/agent-city-cloud.js is missing")
        assets = os.path.join(self.repo.plugin_bin, "agent-city-assets")
        os.makedirs(os.path.join(assets, "vendor"))
        os.makedirs(os.path.join(assets, "characters", "Textures"))
        for rel, text in (("vendor/three.min.js", "/* three */"), ("characters/a.glb", "glb"),
                          ("characters/Textures/colormap.png", "png"), ("License.txt", "CC0")):
            with open(os.path.join(assets, rel), "w") as fh:
                fh.write(text)
        self.out = os.path.join(self.repo.base, "site-out")
        self.npx_log = os.path.join(self.repo.base, "npx.log")
        for name in ("npx", "wrangler"):
            stub = os.path.join(self.repo.bin, name)
            with open(stub, "w") as fh:
                fh.write("#!/bin/sh\necho \"%s $@\" >> '%s'\n" % (name, self.npx_log))
            os.chmod(stub, 0o755)

    def build(self, *args):
        env = {"AGENT_CITY_HOME": os.path.join(self.repo.base, "cityhome"),
               "AGENT_CITY_DIR": os.path.join(self.repo.base, "city")}
        return self.repo.run("agent-city.sh", "cloud-build", *args, env=env, timeout=60)

    def read(self, *parts):
        with open(os.path.join(self.out, *parts), "rb") as fh:
            return fh.read()

    def config(self):
        return json.loads(self.read("wrangler.jsonc").decode("utf-8"))


class TestBuild(BuildCase):
    def test_folder(self):
        result = self.build(self.out, "--d1-id", D1)
        self.assertOk(result)
        with open(os.path.join(self.repo.plugin_bin, "agent-city-cloud.js"), "rb") as fh:
            self.assertEqual(self.read("worker.js"), fh.read())
        with open(os.path.join(self.repo.plugin_bin, "agent-city.html"), "rb") as fh:
            page = fh.read()
        self.assertEqual(self.read("site", "index.html"), page, "the page as it is: the Worker fills it")
        self.assertIn(b"__CITY_LANG__", self.read("site", "index.html"))
        self.assertEqual(self.read("site", "assets", "vendor", "three.min.js"), b"/* three */")
        self.assertEqual(self.read("site", "assets", "characters", "Textures", "colormap.png"), b"png")
        lines = self.lines(result.stdout)
        self.assertIn("CLOUD: built %s" % self.out, lines)
        self.assertIn("CLOUD: deploy it yourself: cd %s && npx wrangler deploy" % self.out, lines)

    def test_wrangler_config(self):
        self.assertOk(self.build(self.out, "--d1-id", D1))
        cfg = self.config()
        self.assertEqual(cfg["name"], "agent-city-page")
        self.assertEqual(cfg["main"], "worker.js")
        self.assertRegex(cfg["compatibility_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIs(cfg["keep_vars"], True)
        self.assertIs(cfg["workers_dev"], True)
        self.assertEqual(cfg["assets"], {"directory": "./site", "binding": "ASSETS", "run_worker_first": True})
        self.assertEqual(cfg["d1_databases"], [{"binding": "DB", "database_name": "agent-city",
                                                "database_id": D1}])
        self.assertIn(cfg["vars"]["CITY_LANG"], ("zh", "en"))
        self.assertTrue(cfg["vars"]["CITY_ASSET_V"])
        self.assertEqual(set(cfg["vars"]), {"CITY_LANG", "CITY_ASSET_V"},
                         "the Access values are typed in the dashboard, never written to a file")

    def test_names(self):
        self.assertOk(self.build(self.out, "--d1-id", D1, "--d1-name", "relay-db", "--name", "my-city"))
        cfg = self.config()
        self.assertEqual((cfg["name"], cfg["d1_databases"][0]["database_name"]), ("my-city", "relay-db"))

    def test_bad_or_missing_id_writes_nothing(self):
        for args in ((self.out,), (self.out, "--d1-id", "not-an-id"), (self.out, "--d1-id", ""),
                     ("--d1-id", D1)):
            result = self.build(*args)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse(os.path.exists(self.out))

    def test_built_anew(self):
        self.assertOk(self.build(self.out, "--d1-id", D1))
        stale = os.path.join(self.out, "site", "assets", "old.glb")
        with open(stale, "w") as fh:
            fh.write("old")
        self.assertOk(self.build(self.out, "--d1-id", D1))
        self.assertFalse(os.path.exists(stale))

    def test_no_wrangler_no_secret(self):
        self.assertOk(self.build(self.out, "--d1-id", D1))
        self.assertFalse(os.path.exists(self.npx_log), "cloud-build never runs npx or wrangler")
        text = self.read("wrangler.jsonc").decode("utf-8")
        for word in ("ACCESS_AUD", "ACCESS_TEAM", "TEAM_KEY", "CITY_USER", "@"):
            self.assertNotIn(word, text)


class TestDeployIsTheOwners(BuildCase):
    def test_refuses_without_a_terminal(self):
        env = {"AGENT_CITY_HOME": os.path.join(self.repo.base, "cityhome")}
        result = self.repo.run("agent-city.sh", "cloud-deploy", env=env, stdin=D1 + "\n", timeout=30)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("CLOUD: run this yourself in your own terminal", result.stdout + result.stderr)
        self.assertFalse(os.path.exists(self.npx_log), "nothing may be deployed by an agent")
        self.assertFalse(os.path.exists(os.path.join(self.repo.base, "cityhome", "cloud-site")))

    def test_it_would_deploy_with_wrangler(self):
        with open(os.path.join(ROOT, "bin", "agent-city.sh")) as fh:
            src = fh.read()
        self.assertIn("npx wrangler deploy", src)
        self.assertNotRegex(src, r"(?m)^\s*(npx\s+)?wrangler\s+login",
                            "the script never runs a login: the owner types it himself")


class TestSetupSteps(unittest.TestCase):
    def setUp(self):
        with open(SETUP) as fh:
            self.text = fh.read()
        self.sections = re.findall(r"(?ms)^## (\d+)\. ([^\n]+)\n(.*?)(?=^## |\Z)", self.text)

    def section(self, word):
        hits = [(n, title, body) for n, title, body in self.sections if word.lower() in title.lower()]
        self.assertTrue(hits, "no section with %r in its title" % word)
        return hits[0]

    def test_old_sections_stay(self):
        titles = [t for _, t, _ in self.sections]
        for word in ("Make a Cloudflare account", "Make the relay", "Set the team key",
                     "Join this computer", "Change the key", "Remove the relay"):
            self.assertTrue([t for t in titles if word in t], word)

    def test_numbers_run_on(self):
        nums = [int(n) for n, _, _ in self.sections]
        self.assertEqual(nums, list(range(1, len(nums) + 1)))
        self.assertGreaterEqual(len(nums), 14, "four or more new sections after the ten relay ones")

    def test_every_section_says_what_you_should_see(self):
        for n, title, body in self.sections:
            self.assertIn("You should see", body, "section %s. %s" % (n, title))

    def test_turn_it_on(self):
        _, _, body = self.section("cloud page on")
        self.assertIn("CITY_USER", body)
        self.assertIn("agent-city-relay.js", body, "the new relay code is pasted again")
        self.assertRegex(body, r"(?i)your e-?mail")

    def test_deploy(self):
        _, _, body = self.section("Deploy")
        self.assertIn("npx wrangler login", body)
        self.assertIn("cloud-deploy", body)
        self.assertRegex(body, r"(?i)database id")
        self.assertRegex(body, r"(?i)never .*(chat|agent)")

    def test_login(self):
        _, _, body = self.section("login")
        self.assertIn("Enable Cloudflare Access", body)
        self.assertIn("ACCESS_TEAM", body)
        self.assertIn("ACCESS_AUD", body)
        self.assertRegex(body, r"(?i)one-time (code|pin)")

    def test_check(self):
        _, _, body = self.section("Check the cloud page")
        self.assertIn("CLOUD: on", body)
        self.assertRegex(body, r"(?i)phone")
        self.assertRegex(body, r"(?i)starts? by itself|no need to (type|start)")

    def test_turn_it_off(self):
        _, _, body = self.section("cloud page off")
        self.assertIn("CITY_USER", body)

    def test_cost_line(self):
        self.assertIn("100,000", self.text)
        self.assertRegex(self.text, r"(?i)free plan")

    # ---- cloud-city-2: two more sections, talk on and talk off (T8, and ADD 1 of the main manager) ----

    def test_talk_sections_come_after_the_cloud_page_ones(self):
        nums = {title: int(n) for n, title, _ in self.sections}
        on = [n for t, n in nums.items() if re.search(r"(?i)talk", t) and re.search(r"(?i)\bon\b", t)]
        off = [n for t, n in nums.items() if re.search(r"(?i)talk", t) and re.search(r"(?i)\boff\b", t)]
        self.assertEqual((on, off), ([16], [17]), "16. Turn talking on, 17. Turn talking off")

    def test_talk_on_steps(self):
        _, _, body = self.section("talking on")
        self.assertIn("TALK_KEY", body)
        self.assertIn("openssl rand -hex 24", body)
        self.assertRegex(body, r"(?i)Secret")
        self.assertIn("agent-city-relay.js", body, "the new relay code is pasted again")
        self.assertIn("cloud-deploy", body, "the new page code is deployed again")
        self.assertIn("cloud-talk on", body)
        self.assertIn("CLOUD TALK: on", body)
        self.assertRegex(body, r"(?i)hidden")
        self.assertRegex(body, r"(?i)each machine|every machine|on that machine")
        self.assertRegex(body, r"(?i)never .*(chat|agent)", "the talk key is never typed into a chat with an agent")
        self.assertRegex(body, r"(?i)off by default|stays off")

    def test_talk_on_says_what_it_means(self):
        _, _, body = self.section("talking on")
        self.assertRegex(body, r"(?is)(whoever|anyone who) can log in as you.{0,120}(type|talk) to your agents",
                         "in plain words: who can log in as the owner can type to his agents")
        self.assertRegex(body, r"(?i)machines? with talk(ing)? on")
        self.assertRegex(body, r"(?i)session duration", "where to set how long a login lasts")
        self.assertRegex(body, r"(?i)Zero Trust")
        self.assertRegex(body, r"(?i)short")
        self.assertRegex(body, r"(?is)e-?mail account.{0,160}(safe|two-step|2-step|second step|password)")
        self.assertRegex(body, r"(?i)only text|text only")
        self.assertRegex(body, r"(?i)7 days")
        self.assertRegex(body, r"(?i)approv", "approving a permission request stays on the machine")

    def test_talk_off_says_every_way_to_stop_it(self):
        _, _, body = self.section("talking off")
        self.assertIn("cloud-talk off", body)
        self.assertIn("CLOUD TALK: off", body)
        self.assertIn("TALK_KEY", body)
        self.assertRegex(body, r"(?i)delete", "delete TALK_KEY: off for every machine")
        self.assertRegex(body, r"(?i)(end|revoke|log out|sign out).{0,80}(session|login)|(session|login).{0,80}(end|revoke)",
                         "end the Access session")
        self.assertRegex(body, r"(?i)one machine|that machine|this machine")
        self.assertRegex(body, r"(?i)all machines|every machine")

    def test_the_cloud_page_section_no_longer_says_you_cannot_chat(self):
        _, _, body = self.section("cloud page on")
        self.assertNotRegex(body, r"(?i)you cannot chat or answer from it\.")
        self.assertRegex(body, r"(?i)section 16")

    def test_no_real_address_or_key(self):
        for word in ("maverickleeweilin88", "gmail.com"):
            self.assertNotIn(word, self.text)


class TestRequirementLines(unittest.TestCase):
    def setUp(self):
        with open(REQ) as fh:
            self.text = fh.read()

    def test_cloud_page_section(self):
        self.assertIn("## Cloud page", self.text)
        body = self.text[self.text.index("## Cloud page"):self.text.index("## Relay setup")]
        for word in ("One reducer", "CITY_USER", "city_view", "Cloudflare Access", "403",
                     "View only", "Only joined repos", "CLOUD_KEEP", "Auto-start", "CLOUD: on"):
            self.assertIn(word, body, word)

    def test_old_rules_are_replaced_not_left(self):
        self.assertNotIn("There is no shared city page on the internet.", self.text)
        self.assertNotIn("the relay carries events only, never orders", self.text)
        # cloud-city-2 (owner, 2026-10-01): a message from the cloud page is an order, as chat text only.
        self.assertNotIn("never orders", self.text)
        self.assertNotIn("never through the relay or the cloud page, which carry no chat text", self.text)
        self.assertNotIn("has no route that acts and never writes a row", self.text)

    def test_talk_rules(self):
        self.assertIn("### Talk", self.text)
        body = self.text[self.text.index("### Talk"):self.text.index("## Relay setup")]
        for word in ("TALK_KEY", "cloud-talk on", "cloud-talk off", "CLOUD TALK: on", "city_msg", "city_chat",
                     "/api/chat/send", "X-City-Page", "7 days", "200 rows", "60 s", "10 min", "cloud-seen",
                     "4,000", "30 messages in 5 minutes", "300 a day", "以后开放", "在路上", "重发",
                     "那台电脑没开", "这个会话已经结束", "那台电脑不接收云端消息", "owner not seen",
                     "never calls a machine", "team key alone"):
            self.assertIn(word, self.text[self.text.index("## Cloud page"):self.text.index("## Relay setup")], word)
        self.assertRegex(body, r"(?i)nothing queued")
        orders = [l for l in self.text.splitlines() if l.startswith("- Orders")]
        self.assertEqual(len(orders), 1)
        self.assertRegex(orders[0], r"(?i)text for a session's chat queue only")
        self.assertRegex(orders[0], r"(?i)team key alone never makes a message")


if __name__ == "__main__":
    unittest.main()
