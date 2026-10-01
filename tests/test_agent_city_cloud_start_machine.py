"""Failing tests, cloud-city-3 slice W3: the machine takes a start order from
the cloud page and opens ONE session with the function of its own button
(requirements/city.md, "Cloud page", "Start"; approved design D1-D16 in
agent_state.txt and in commit 9c8479d). No test opens a real session: the
opener is a fake function, or a fake `orca` first on PATH that only logs.

bin/agent_city_relay.py
  The start file: <AGENT_CITY_HOME>/cloud-start, one relay HOST per line (the
  relays this machine takes start orders from). Mode 0600. Hosts only, never
  a key: the key is the talk key of the talk file.
      read_start(path) -> a set of hosts. Missing or broken file -> set(). A
          blank line and a "#" line are skipped; a line with more than one
          word is skipped too (never read as on).
      set_start(path, host, on) -> HOST is in the file (on true) or not; the
          whole file at once (tmp + mv), mode 0600; the file is removed when
          the last host goes. Never raises.
      SLOW_SEC = 15.0
  RelayHub(..., start_file=None, slow_fn=None, slow_sec=SLOW_SEC)
      hub.start_file: the path (the talk source reads it before every sync,
          so on / off works with the next sync, no restart).
      slow_fn() true -> a team's next sync is due slow_sec after the last one
          instead of relay_sec (talk_soon still wins: TALK_SOON_SEC). slow_fn
          None or false, or raising: relay_sec as before.

bin/agent_city.py
  cloud_start_path() -> the start file: next to the talk file
      ($AGENT_CITY_HOME/cloud-start, else ~/.claude/agent-city/cloud-start).
  CLOUD_ORDER_AGE_MS = 90000, CLOUD_ORDER_MAX = 10, CLOUD_ORDER_SEC = 3600.0,
  CLOUD_ORDER_TAKE = 3

  CityState(..., cloud_orders_path=None)
  CityState.cloud_order(oid, terr, force, age_ms, terrs, now) -> {"oid", "state"[, "why"][, "info"]}
      One click on the cloud page's add-agent button for territory TERR. NOW
      is monotonic seconds (what add_agent takes). TERRS = the territory ids
      of the repos joined to the relay it came from. The ONE thing it ever
      does with an order is CityState.add_agent(terr, now, force): the
      function of the local button (the folder from this server's own world,
      the role from the lock, agent_command, open_fn). Nothing of the order
      reaches a shell, a path, a flag, the opener's arguments or the
      server's options.
        oid is not a string of 16..64 of A-Z a-z 0-9 _ -     -> "failed", why "refused";
            nothing is written or logged
        oid seen before (this run, or in the orders file)     -> never opened again:
            its answer of now (see below); an oid in the file with no final
            answer (the server restarted in the middle) -> "failed", why "restart"
        terr is not a string of 8 of 0-9 a-f, force is not a bool, age_ms is
            not a finite number (a bool is not a number)      -> "failed", why "refused"
        age_ms over CLOUD_ORDER_AGE_MS                        -> "failed", why "off"
        terr not in TERRS (a repo that is not joined to that relay), or no
            territory of this world                           -> "failed", why "refused"
        CLOUD_ORDER_MAX orders already let in during the last
            CLOUD_ORDER_SEC seconds (this machine's own count, whatever the
            cloud says)                                       -> "failed", why "flood"
        the oid cannot be written to the orders file          -> "failed", why "off"
        else add_agent, and its answer in the order's words:
            200 opening  -> "opening", info {"name", "role"}
            200 cap      -> "cap", info {"ram", "cpu", "max"} (nothing opened;
                            the owner's yes is a NEW order with force true)
            200 plain    -> "failed", why "no-orca" (the command line is
                            never part of the answer)
            409 gone     -> "failed", why "gone" (never the folder's path)
            409 busy     -> "failed", why "busy"
            502 failed   -> "failed", why "orca", info {"detail": the
                            opener's reason with every path cut to its last
                            part, at most 200 characters}
            400, 404     -> "failed", why "refused"
      Later, by itself: the new session's first line (add_agent's "done")
        -> "opened" (info as "opening"); ADD_WAIT_SEC with no new session
        (add_agent's "late") -> "failed", why "late".
      The orders file (cloud_orders_path, one JSON line per change, mode
        0600, on disk before the opener runs): {"oid"} when the order is let
        in, then {"oid", "state"[, "why"]} for every answer. Ids and states
        only: never a path, a name or a command.
      decisions.jsonl: one row when an order is let in and one per answer:
        {"t", "by": "owner", "verb": "add-agent", "via": "cloud", "oid",
         "repo" (the repo's name, never a path), "force", "outcome"[, "why"]}
        outcome: taken | opening | opened | cap | failed. An order refused
        before it was let in (a good oid) gets one row (failed, its why,
        repo ""). An oid handed down again logs nothing new. A click on the
        local page logs nothing, as today.
      The local page sees a cloud order like its own click: the "adding"
        events of add_agent, nothing new.
  CityState.cloud_order_answers(oids) -> {oid: answer} for the oids this
      server knows (an unknown oid is left out). No side effect.

  The cloud world (CityState.cloud_world): every territory carries "here":
      true | false, as the local view does. Never a path.

  CloudUploader (the hub's talk source), only for a relay whose host is in
  the start file AT THAT MOMENT (and has a talk key: the hub asks for talk
  only then):
      talk_take: the talk always carries "start" (a dict; so talk_take never
          gives None for such a relay): {"acks": [...]} or {}. acks =
          {"oid", "state"[, "why"][, "info"]} for every order handed down,
          and again whenever its answer changes; an ack rides until a sync
          the relay answered has carried it.
      talk_sent: the reply's talk["start"] is {"state": "on", "orders":
          [...]} -> each order (CLOUD_ORDER_TAKE at most; only oid, terr,
          force and age are read) goes to city.cloud_order.
      talk_soon: true while an order's answer waits to go up.
      Host not in the start file: no "start" in the talk, and orders in a
      reply are never read.
  serve: CityState gets cloud_orders_path=<city dir>/cloud-orders; the hub
      gets start_file=cloud_start_path() and the slow beat; new option
      --slow-sec S (default SLOW_SEC).
  STAY UP: the server does not stop itself for being idle while a joined
      relay says the cloud page is on AND (a live session is in the roster,
      as before, OR that relay's host is in the start file and has a talk
      key). With start on, no page client and no live session it syncs every
      slow-sec seconds instead of relay-sec.

  TEST ONLY, for the E2E on the laptop (a real session must open in a repo
  Orca already knows, and nothing may be written into that repo's .secrets):
      RelayHub(..., join_dir=None) and serve --join-dir DIR. With a join dir
      the join file of a repo is DIR/<the repo folder's own name> (the same
      two lines, address= and key=) and the repo's own
      .secrets/agent-city-relay is not read at all (offer, seed and the
      joined list alike). Without it: exactly as before. Never set by
      agent-city.sh; no command, hook or page ever passes it.

Every test uses a fake relay on 127.0.0.1 and temp folders. Never a real key.

Run: python3 -m unittest tests.test_agent_city_cloud_start_machine </dev/null
"""

import json
import os
import shutil
import stat
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

from relayhelp import hook_line, join, make_repo  # noqa: E402
from test_agent_city_server import wait_for  # noqa: E402
from test_agent_city_cloud_upload import ClientCase  # noqa: E402
from test_agent_city_cloud_talk_machine import TALK, TalkCase  # noqa: E402
from cityhelp import Mains  # noqa: E402
import agent_city as ac  # noqa: E402
import agent_city_relay as rl  # noqa: E402

MARK = "MARKc3x9"
CONF = "main_manager=opus-5.5:high\npermission_mode=auto\n"


def need(case, mod, name):
    case.assertTrue(hasattr(mod, name), "%s.%s is missing" % (mod.__name__, name))
    return getattr(mod, name)


def line(ev, sid, repo, aid="", role=""):
    return {"ev": ev, "sid": sid, "aid": aid, "at": "", "tool": "Read", "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


def oid(n):
    return "oid-%016d" % n


# --------------------------------------------------------------- cloud_order

class OrderCase(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_start_"))
        self.calls = []                 # every call of the fake opener: (folder, title, command)
        self.answer = (True, "")
        self.mains = Mains()
        self.kind = "orca"
        self.res = {"ram": 10, "cpu": 10, "max": 80, "ok": True}
        self.now = 1000.0               # monotonic seconds
        self.seen = os.path.join(self.base, "city", "cloud-orders")
        self.decisions = os.path.join(self.base, "decisions.jsonl")
        self.shop = self.repo("shop")
        self.state = self.make()
        self.terr = self.known(self.shop)
        self.terrs = {self.terr}

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def repo(self, name, conf=CONF):
        folder = os.path.join(self.base, name)
        os.makedirs(os.path.join(folder, ".git"))
        if conf is not None:
            with open(os.path.join(folder, "agent.conf"), "w") as fh:
                fh.write(conf)
        return os.path.join(folder, ".git")

    def opener(self, folder, title, command):
        self.calls.append((folder, title, command))
        return self.answer

    def make(self, **kw):
        args = dict(world_path=None, token="tok", count_fn=lambda i: 0,
                    balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []},
                    main_fn=self.mains, open_fn=self.opener, kind_fn=lambda folder: self.kind,
                    resources_fn=lambda folder: dict(self.res), cloud_orders_path=self.seen)
        args.update(kw)
        try:
            return ac.CityState(decisions_path=self.decisions, **args)   # never the owner's real decisions file
        except TypeError as exc:
            self.fail("CityState takes no cloud_orders_path yet: %s" % exc)

    def feed(self, *lines, state=None):
        for obj in lines:
            (state or self.state).feed_line(obj, self.now)

    def known(self, identity, sid="old1", state=None):
        self.feed(line("UserPromptSubmit", sid, identity), line("Stop", sid, identity), state=state)
        return ac.territory_id(identity)

    def order(self, oid_, terr=None, force=False, age=1000, terrs=None, state=None):
        state = state or self.state
        self.assertTrue(hasattr(state, "cloud_order"), "CityState.cloud_order is missing")
        self.now += 1.0
        return state.cloud_order(oid_, self.terr if terr is None else terr, force, age,
                                 self.terrs if terrs is None else terrs, self.now)

    def seen_lines(self):
        try:
            with open(self.seen, encoding="utf-8") as fh:
                return [json.loads(l) for l in fh if l.strip()]
        except OSError:
            return []

    def rows(self):
        try:
            with open(self.decisions, encoding="utf-8") as fh:
                return [json.loads(l) for l in fh if l.strip()]
        except OSError:
            return []

    def client(self):
        c = self.state.add_client()
        while not c.queue.empty():
            c.queue.get_nowait()
        return c

    @staticmethod
    def events(client, kind="adding"):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait().decode("utf-8")
            if "data:" in raw:
                msg = json.loads(raw.split("data:", 1)[1])
                if msg.get("type") == kind:
                    out.append(msg)
        return out


class TestOpens(OrderCase):
    def test_it_opens_one_session_as_the_local_button_does(self):
        got = self.order(oid(1))
        self.assertEqual(got, {"oid": oid(1), "state": "opening", "info": {"name": "shop Manager", "role": "main"}})
        self.assertEqual(len(self.calls), 1, "one order = one session")
        folder, title, command = self.calls[0]
        self.assertEqual(folder, os.path.dirname(self.shop))
        self.assertEqual(title, "shop Manager")
        self.assertEqual(command, ac.agent_command("shop Manager", os.path.dirname(self.shop), None),
                         "the same fixed line as the local button's")

    def test_it_is_the_same_function(self):
        seen = []
        real = self.state.add_agent

        def spy(terr, now, force=False):
            seen.append((terr, force))
            return real(terr, now, force)
        self.state.add_agent = spy
        self.order(oid(1))
        self.assertEqual(seen, [(self.terr, False)], "cloud_order calls add_agent once: no second way to open a session")

    def test_a_live_main_manager_means_a_helper(self):
        self.mains[self.shop] = "old1"
        got = self.order(oid(1))
        self.assertEqual(got["info"], {"name": "shop Helper", "role": "helper"})
        self.assertEqual(self.calls[0][1], "shop Helper")

    def test_never_a_task_manager(self):
        self.order(oid(1))
        self.assertNotIn("AGENT_ROLE", self.calls[0][2])
        self.assertNotIn("task", self.calls[0][1].lower())

    def test_the_local_page_sees_it_like_its_own_click(self):
        page = self.client()
        self.order(oid(1))
        self.assertEqual([(e["state"], e.get("name")) for e in self.events(page)], [("opening", "shop Manager")])
        self.feed(line("UserPromptSubmit", "new1", self.shop))
        self.assertEqual([e["state"] for e in self.events(page)], ["done"])

    def test_opened_when_the_new_session_shows_up(self):
        self.order(oid(1))
        self.feed(line("UserPromptSubmit", "new1", self.shop))
        self.assertTrue(hasattr(self.state, "cloud_order_answers"), "CityState.cloud_order_answers is missing")
        answers = self.state.cloud_order_answers([oid(1), oid(2)])
        self.assertEqual(answers, {oid(1): {"oid": oid(1), "state": "opened", "info": {"name": "shop Manager", "role": "main"}}})
        self.assertEqual(self.order(oid(1))["state"], "opened", "handed down again: its answer of now")
        self.assertEqual(len(self.calls), 1)

    def test_late_when_nobody_shows_up(self):
        self.order(oid(1))
        self.state.sweep_adding(self.now + ac.ADD_WAIT_SEC + 1)
        got = self.state.cloud_order_answers([oid(1)])[oid(1)]
        self.assertEqual((got["state"], got.get("why")), ("failed", "late"))

    def test_a_local_click_is_no_order(self):
        code, body = self.state.add_agent(self.terr, self.now)
        self.assertEqual((code, body["state"]), (200, "opening"))
        self.feed(line("UserPromptSubmit", "new1", self.shop))
        self.assertEqual(self.state.cloud_order_answers([oid(1)]), {})
        self.assertEqual(self.rows(), [], "a click on the local page logs nothing, as today")
        self.assertEqual(self.seen_lines(), [])

    def test_without_an_orders_file_it_still_works(self):
        state = self.make(cloud_orders_path=None)
        self.known(self.shop, state=state)
        got = self.order(oid(1), state=state)
        self.assertEqual(got["state"], "opening")
        self.assertEqual(self.order(oid(1), state=state)["state"], "opening")
        self.assertEqual(len(self.calls), 1)


class TestAnswers(OrderCase):
    def test_over_the_cap_asks_first(self):
        self.res = {"ram": 86, "cpu": 41, "max": 80, "ok": False}
        got = self.order(oid(1))
        self.assertEqual(got, {"oid": oid(1), "state": "cap", "info": {"ram": 86, "cpu": 41, "max": 80}})
        self.assertEqual(self.calls, [], "nothing opens by itself")
        yes = self.order(oid(2), force=True)
        self.assertEqual(yes["state"], "opening", "the owner's yes is a second order")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.order(oid(1))["state"], "cap", "the first order stays what it was")

    def test_no_orca_never_sends_the_command_up(self):
        self.kind = "plain"
        got = self.order(oid(1))
        self.assertEqual(got, {"oid": oid(1), "state": "failed", "why": "no-orca"})
        self.assertEqual(self.calls, [])

    def test_folder_gone_never_sends_the_path_up(self):
        shutil.rmtree(os.path.dirname(self.shop))
        got = self.order(oid(1))
        self.assertEqual(got, {"oid": oid(1), "state": "failed", "why": "gone"})
        self.assertNotIn(self.base, json.dumps(got))
        self.assertEqual(self.calls, [])

    def test_orca_refused_says_its_words_without_paths(self):
        self.answer = (False, "orca: cannot open /Users/owner/secret/place/shop: permission denied " + "x" * 400)
        got = self.order(oid(1))
        self.assertEqual((got["state"], got["why"]), ("failed", "orca"))
        detail = got["info"]["detail"]
        self.assertIn("orca: cannot open", detail)
        self.assertNotIn("/Users/owner/secret", detail)
        self.assertLessEqual(len(detail), 200)
        self.assertEqual(set(got["info"]), {"detail"})

    def test_the_opener_raises(self):
        def boom(folder, title, command):
            raise RuntimeError("no orca here")
        self.state.open_fn = boom
        got = self.order(oid(1))
        self.assertEqual((got["state"], got["why"]), ("failed", "orca"))

    def test_busy_while_another_open_is_under_way(self):
        self.state.add_agent(self.terr, self.now)           # the local button, a moment before
        got = self.order(oid(1))
        self.assertEqual(got, {"oid": oid(1), "state": "failed", "why": "busy"})
        self.assertEqual(len(self.calls), 1)

    def test_a_failed_open_frees_the_repo(self):
        self.answer = (False, "no")
        self.order(oid(1))
        self.answer = (True, "")
        self.assertEqual(self.order(oid(2))["state"], "opening")


class TestRefused(OrderCase):
    def refused(self, got, why="refused"):
        self.assertEqual((got["state"], got.get("why")), ("failed", why), got)
        self.assertEqual(self.calls, [], "a refused order never reaches the opener")

    def test_a_repo_that_is_not_joined_to_that_relay(self):
        other = self.repo("private")
        terr2 = self.known(other, sid="px1")
        self.refused(self.order(oid(1), terr=terr2))
        self.refused(self.order(oid(2), terr=terr2, terrs=set()))
        self.refused(self.order(oid(3), terrs=frozenset()))

    def test_a_territory_this_machine_does_not_have(self):
        self.refused(self.order(oid(1), terr="0badc0de", terrs={"0badc0de", self.terr}))

    def test_terr_is_a_territory_id_only(self):
        folder = os.path.dirname(self.shop)
        bad = [folder, self.shop, "../shop", "shop", "/bin/sh", self.terr.upper(), self.terr + "0", self.terr[:7],
               self.terr + "\n", " " + self.terr, 7, None, [self.terr], {"id": self.terr}, True]
        for i, terr in enumerate(bad):
            terrs = {self.terr}
            if isinstance(terr, str):
                terrs.add(terr)
            self.refused(self.order(oid(i + 1), terr=terr, terrs=terrs))

    def test_force_is_a_bool(self):
        for i, force in enumerate(("yes", 1, 0, None, "true", [True])):
            self.refused(self.order(oid(i + 1), force=force))

    def test_age_is_a_number(self):
        for i, age in enumerate((None, "1000", True, float("nan"), float("inf"), [1])):
            self.refused(self.order(oid(i + 1), age=age))

    def test_a_bad_oid_writes_nothing(self):
        for bad in ("short", "x" * 65, "has space 0000000000", "../../etc/passwd000", "semi;colon0000000000", 5, None, ["a"]):
            got = self.state.cloud_order(bad, self.terr, False, 1000, self.terrs, self.now)
            self.assertEqual((got["state"], got.get("why")), ("failed", "refused"), bad)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.seen_lines(), [])
        self.assertEqual(self.rows(), [])

    def test_too_old_is_never_opened(self):
        late = need(self, ac, "CLOUD_ORDER_AGE_MS")
        self.assertEqual(late, 90000)
        self.refused(self.order(oid(1), age=late + 1), why="off")
        self.assertEqual(self.order(oid(2), age=late)["state"], "opening")

    def test_ten_an_hour_on_this_machine(self):
        self.assertEqual((need(self, ac, "CLOUD_ORDER_MAX"), need(self, ac, "CLOUD_ORDER_SEC")), (10, 3600.0))
        self.res = {"ram": 99, "cpu": 99, "max": 80, "ok": False}       # every order is answered "cap": the repo is never held
        for i in range(10):
            self.assertEqual(self.order(oid(i + 1))["state"], "cap", i)
        got = self.order(oid(11), force=True)
        self.assertEqual((got["state"], got.get("why")), ("failed", "flood"))
        self.assertEqual(self.calls, [], "over this machine's own cap nothing opens, whatever the cloud says")
        self.now += 3600.0
        self.assertEqual(self.order(oid(12), force=True)["state"], "opening", "an hour later it takes orders again")

    def test_a_refused_order_does_not_count(self):
        self.res = {"ram": 99, "cpu": 99, "max": 80, "ok": False}
        for i in range(15):
            self.order(oid(100 + i), terr="0badc0de")
        self.assertEqual(self.order(oid(1))["state"], "cap")


class TestNothingOfTheOrderReachesTheOpener(OrderCase):
    """ADD2 (the gate, 2026-10-01): nothing from an order can appear in the argv of the opener."""

    def test_the_opener_gets_this_machines_own_words(self):
        mark_oid = "oid_" + MARK + "-0000000000001"
        got = self.order(mark_oid, force=True)
        self.assertEqual(got["state"], "opening")
        folder, title, command = self.calls[0]
        blob = "\n".join((folder, title, command))
        for word in (MARK, mark_oid, self.terr, "force", "True"):
            self.assertNotIn(word, blob)
        self.assertEqual((folder, title), (os.path.dirname(self.shop), "shop Manager"))
        self.assertEqual(command, ac.agent_command("shop Manager", os.path.dirname(self.shop), None))

    def test_the_real_opener_runs_a_fixed_argument_list(self):
        seen = []

        class Done:
            returncode = 0
            stdout = b""
            stderr = b""

        def fake_run(args, **kw):
            seen.append((list(args), kw))
            return Done()
        state = self.make(open_fn=None)                     # the real open_session, its subprocess.run is the fake
        self.known(self.shop, state=state)
        mark_oid = "oid_" + MARK + "-0000000000002"
        with mock.patch.object(ac.subprocess, "run", fake_run):
            got = self.order(mark_oid, force=True, state=state)
        self.assertEqual(got["state"], "opening", got)
        launches = [a for a, kw in seen if "launch" in a]
        self.assertEqual(len(launches), 1, seen)
        args = launches[0]
        folder = os.path.dirname(self.shop)
        self.assertEqual(args[0], "bash")
        self.assertEqual(args[2:], ["launch", folder, "shop Manager", ac.agent_command("shop Manager", folder, None)])
        for a, kw in seen:
            self.assertFalse(kw.get("shell"), "never a shell line")
            for word in a:
                for bad in (MARK, mark_oid, self.terr):
                    self.assertNotIn(bad, word)

    def test_cloud_order_has_no_room_for_more(self):
        import inspect
        params = list(inspect.signature(ac.CityState.cloud_order).parameters) if hasattr(ac.CityState, "cloud_order") \
            else self.fail("CityState.cloud_order is missing")
        self.assertEqual(params, ["self", "oid", "terr", "force", "age_ms", "terrs", "now"],
                         "an order is an id, a territory id and a yes / no: no name, path, model, flag or text")


class TestOnce(OrderCase):
    def test_handed_down_three_times_opened_once(self):
        first = self.order(oid(1))
        again = [self.order(oid(1)), self.order(oid(1), force=True, terr="0badc0de")]
        self.assertEqual([first] + again, [first] * 3)
        self.assertEqual(len(self.calls), 1)

    def test_the_oid_is_on_disk_before_the_opener_runs(self):
        order = []

        def opener(folder, title, command):
            order.append([l.get("oid") for l in self.seen_lines()])
            return True, ""
        self.state.open_fn = opener
        self.order(oid(1))
        self.assertEqual(order, [[oid(1)]])
        self.assertEqual(stat.S_IMODE(os.stat(self.seen).st_mode), 0o600)

    def test_the_orders_file_holds_ids_and_states_only(self):
        self.order(oid(1))
        self.feed(line("UserPromptSubmit", "new1", self.shop))
        with open(self.seen, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn(self.base, text)
        self.assertNotIn("claude", text)
        self.assertNotIn("Manager", text)
        for row in self.seen_lines():
            self.assertLessEqual(set(row), {"oid", "state", "why"}, row)
        self.assertEqual([r.get("state") for r in self.seen_lines()], [None, "opening", "opened"])

    def test_no_file_no_open(self):
        os.makedirs(self.seen)                              # a folder where the file should be: it cannot be written
        got = self.order(oid(1))
        self.assertEqual((got["state"], got.get("why")), ("failed", "off"))
        self.assertEqual(self.calls, [], "no promise of once: nothing opens")

    def test_a_restart_in_the_middle_never_opens_it_again(self):
        def crash(folder, title, command):
            raise SystemExit("the server dies while the terminal opens")
        self.state.open_fn = crash
        with self.assertRaises(SystemExit):
            self.order(oid(1))
        self.assertEqual([l.get("oid") for l in self.seen_lines()], [oid(1)])
        again = self.make()                                 # the server starts again, the same orders file
        self.known(self.shop, state=again)
        got = self.order(oid(1), state=again)
        self.assertEqual(got, {"oid": oid(1), "state": "failed", "why": "restart"})
        self.assertEqual(self.calls, [])
        self.assertEqual(self.order(oid(1), state=again), got)

    def test_a_restart_while_it_was_opening_says_restart(self):
        self.order(oid(1))
        again = self.make()
        self.known(self.shop, state=again)
        got = self.order(oid(1), state=again)
        self.assertEqual((got["state"], got.get("why")), ("failed", "restart"),
                         "the new server cannot know whether that session came up")
        self.assertEqual(len(self.calls), 1)

    def test_a_restart_keeps_a_final_answer(self):
        self.order(oid(1))
        self.feed(line("UserPromptSubmit", "new1", self.shop))                  # opened
        self.res = {"ram": 86, "cpu": 41, "max": 80, "ok": False}
        self.order(oid(2))                                                      # cap
        self.kind = "plain"
        self.order(oid(3))                                                      # failed, no-orca
        again = self.make()
        self.known(self.shop, state=again)
        got = [self.order(oid(i), state=again) for i in (1, 2, 3)]
        self.assertEqual([(g["state"], g.get("why")) for g in got],
                         [("opened", None), ("cap", None), ("failed", "no-orca")])
        self.assertEqual(len(self.calls), 1)


class TestLog(OrderCase):
    def test_every_order_and_its_outcome(self):
        self.order(oid(1))
        self.order(oid(1))                                  # handed down again: nothing new
        self.feed(line("UserPromptSubmit", "new1", self.shop))
        rows = self.rows()
        self.assertEqual([r["outcome"] for r in rows], ["taken", "opening", "opened"])
        for r in rows:
            self.assertEqual((r["by"], r["verb"], r["via"], r["oid"], r["repo"], r["force"]),
                             ("owner", "add-agent", "cloud", oid(1), "shop", False))
            self.assertTrue(r.get("t"))
            self.assertNotIn(self.base, json.dumps(r), "the repo's name, never a path")

    def test_a_failure_says_why(self):
        self.kind = "plain"
        self.order(oid(1), force=True)
        rows = self.rows()
        self.assertEqual([(r["outcome"], r.get("why")) for r in rows], [("taken", None), ("failed", "no-orca")])
        self.assertIs(rows[0]["force"], True)

    def test_a_refused_order_is_logged_once(self):
        self.order(oid(1), terr="0badc0de")
        self.order(oid(1), terr="0badc0de")
        rows = self.rows()
        self.assertEqual([(r["outcome"], r.get("why"), r["repo"]) for r in rows], [("failed", "refused", "")])

    def test_cap_and_late(self):
        self.res = {"ram": 86, "cpu": 41, "max": 80, "ok": False}
        self.order(oid(1))
        self.order(oid(2), force=True)
        self.state.sweep_adding(self.now + ac.ADD_WAIT_SEC + 1)
        got = [(r["oid"], r["outcome"], r.get("why")) for r in self.rows()]
        self.assertEqual(got, [(oid(1), "taken", None), (oid(1), "cap", None), (oid(2), "taken", None),
                               (oid(2), "opening", None), (oid(2), "failed", "late")])


class TestHereGoesUp(OrderCase):
    def test_the_cloud_world_says_here(self):
        away = self.repo("away")
        self.known(away, sid="aw1")
        shutil.rmtree(os.path.dirname(away))                # its folder is not on this machine (any more)
        world = self.state.cloud_world([self.shop, away])
        got = {t["name"]: t.get("here") for t in world["territories"]}
        self.assertEqual(got, {"shop": True, "away": False})
        self.assertNotIn(self.base, json.dumps(world), "never a path")

    def test_cloud_clean_keeps_it(self):
        snap = {"type": "snapshot", "agents": [], "govs": [], "asks": [], "shows": [],
                "world": self.state.cloud_world([self.shop])}
        clean = ac.cloud_clean(snap)
        self.assertIs(clean["world"]["territories"][0]["here"], True)


# ------------------------------------------------- the start file and the hub

class TestStartFile(ClientCase):
    def setUp(self):
        super().setUp()
        self.start_file = os.path.join(self.base, "cityhome", "cloud-start")

    def test_set_and_read(self):
        read, put = need(self, rl, "read_start"), need(self, rl, "set_start")
        self.assertEqual(read(self.start_file), set())
        put(self.start_file, "b.example", True)
        put(self.start_file, "a.example:8787", True)
        put(self.start_file, "a.example:8787", True)
        self.assertEqual(read(self.start_file), {"a.example:8787", "b.example"})
        self.assertEqual(stat.S_IMODE(os.stat(self.start_file).st_mode), 0o600)
        with open(self.start_file) as fh:
            self.assertEqual(sorted(fh.read().split()), ["a.example:8787", "b.example"], "hosts only, each once")
        put(self.start_file, "b.example", False)
        self.assertEqual(read(self.start_file), {"a.example:8787"})
        put(self.start_file, "a.example:8787", False)
        self.assertFalse(os.path.exists(self.start_file), "no host left: no file")
        put(self.start_file, "zz.example", False)
        self.assertFalse(os.path.exists(self.start_file))

    def test_a_broken_file_reads_empty(self):
        os.makedirs(os.path.dirname(self.start_file))
        with open(self.start_file, "wb") as fh:
            fh.write(b"\xff\xfe\x00")
        self.assertEqual(need(self, rl, "read_start")(self.start_file), set())
        with open(self.start_file, "w") as fh:
            fh.write("# a comment\n\nok.example\nhost.example somekey\n")
        self.assertEqual(rl.read_start(self.start_file), {"ok.example"}, "a line with a second word is never read as on")

    def test_the_path_is_next_to_the_talk_file(self):
        with mock.patch.dict(os.environ, {"AGENT_CITY_HOME": os.path.join(self.base, "cityhome")}):
            self.assertEqual(need(self, ac, "cloud_start_path")(), self.start_file)
            self.assertEqual(os.path.dirname(ac.cloud_start_path()), os.path.dirname(ac.cloud_talk_path()))

    def test_the_hub_keeps_the_path(self):
        try:
            hub = self.hub(start_file=self.start_file)
        except TypeError as exc:
            self.fail("RelayHub takes no start_file yet: %s" % exc)
        self.assertEqual(hub.start_file, self.start_file)
        self.assertIsNone(self.hub().start_file)


class TestSlowBeat(ClientCase):
    def setUp(self):
        super().setUp()
        join(self.repo, self.fake.url)
        self.slow = [False]

    def make(self, **kw):
        self.assertEqual(need(self, rl, "SLOW_SEC"), 15.0)
        try:
            hub = self.hub(relay_sec=0.05, slow_fn=lambda: self.slow[0], **kw)
        except TypeError as exc:
            self.fail("RelayHub takes no slow_fn / slow_sec yet: %s" % exc)
        hub.offer(hook_line(self.repo))
        return hub

    def syncs(self):
        return len([r for r in self.fake.requests if r["path"] == "/v1/sync"])

    def test_slow_means_slow_sec_between_two_syncs(self):
        hub = self.make(slow_sec=0.8)
        hub.tick()
        self.slow[0] = True
        before = self.syncs()
        end = time.monotonic() + 0.5
        while time.monotonic() < end:
            hub.tick()
            time.sleep(0.05)
        self.assertEqual(self.syncs(), before, "slow: not before slow_sec has passed")
        time.sleep(0.5)
        hub.tick()
        self.assertEqual(self.syncs(), before + 1)

    def test_not_slow_is_relay_sec(self):
        hub = self.make(slow_sec=30)
        hub.tick()
        time.sleep(0.1)
        hub.tick()
        self.assertEqual(self.syncs(), 2)

    def test_a_broken_slow_fn_is_not_slow(self):
        def boom():
            raise RuntimeError("boom")
        hub = self.hub(relay_sec=0.05, slow_fn=boom, slow_sec=30) if hasattr(rl, "SLOW_SEC") else self.fail("SLOW_SEC is missing")
        hub.offer(hook_line(self.repo))
        hub.tick()
        time.sleep(0.1)
        hub.tick()
        self.assertEqual(self.syncs(), 2)


class TestJoinDir(ClientCase):
    """Test only (the E2E on the laptop): a repo counts as joined with no file in its own .secrets."""

    def setUp(self):
        super().setUp()
        self.joins = os.path.join(self.base, "joins")
        os.makedirs(self.joins)

    def put(self, name="shop"):
        path = os.path.join(self.joins, name)
        with open(path, "w") as fh:
            fh.write("address=%s\nkey=%s\n" % (self.fake.url, self.fake.key))
        os.chmod(path, 0o600)
        return path

    def make(self, **kw):
        try:
            return self.hub(**kw)
        except TypeError as exc:
            self.fail("RelayHub takes no join_dir yet: %s" % exc)

    def test_the_join_is_read_from_that_folder(self):
        self.put()
        hub = self.make(join_dir=self.joins)
        self.assertTrue(hub.offer(hook_line(self.repo)), "DIR/shop is the join file of the repo whose folder is shop")
        hub.tick()
        self.assertEqual(len(self.fake.sent_lines()), 1)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".secrets")), "nothing is written into the repo")

    def test_seed_reads_it_too(self):
        self.put()
        hub = self.make(join_dir=self.joins)
        hub.seed(self.repo)
        hub.tick()
        self.assertEqual(len([r for r in self.fake.requests if r["path"] == "/v1/sync"]), 1)

    def test_the_repos_own_file_is_not_read_then(self):
        join(self.repo, self.fake.url)
        hub = self.make(join_dir=self.joins)                 # an empty join dir
        self.assertFalse(hub.offer(hook_line(self.repo)))
        hub.tick()
        self.assertEqual(self.fake.requests, [])

    def test_without_it_nothing_changes(self):
        self.put()
        hub = self.hub()
        self.assertFalse(hub.offer(hook_line(self.repo)), "no join dir: only <repo>/.secrets/agent-city-relay joins a repo")

    def test_the_command_never_passes_it(self):
        with open(os.path.join(BIN, "agent-city.sh")) as fh:
            self.assertNotIn("join-dir", fh.read(), "a test-only option: the owner's command never sets it")


# ------------------------------------------------ the server, with a fake orca

ORCA = r"""#!/usr/bin/env python3
# A fake orca for the tests: it logs its arguments and opens nothing.
import json, os, sys
with open(os.environ["ORCA_FAKE_LOG"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
mode = "ok"
try:
    with open(os.environ["ORCA_FAKE_LOG"] + ".mode") as fh:
        mode = fh.read().strip() or "ok"
except OSError:
    pass
if sys.argv[1:3] == ["terminal", "create"] and mode == "fail":
    sys.stderr.write("orca: cannot open a terminal in /Users/owner/secret/place/shop: not signed in\n")
    sys.exit(1)
print("[]" if sys.argv[1:3] == ["worktree", "ps"] else "{}")
"""


class StartCase(TalkCase):
    """A real server process; the fake relay hands orders down; `orca` on its PATH is the fake above."""

    def setUp(self):
        super().setUp()
        self.start_file = os.path.join(self.base, "cityhome", "cloud-start")
        self.orca_log = os.path.join(self.base, "orca.log")
        stub = os.path.join(self.base, "stubbin")
        os.makedirs(stub)
        with open(os.path.join(stub, "orca"), "w") as fh:
            fh.write(ORCA)
        os.chmod(os.path.join(stub, "orca"), 0o755)
        self.env = {"PATH": stub + os.pathsep + os.environ.get("PATH", ""), "AGENT_RUNTIME": "orca",
                    "ORCA_FAKE_LOG": self.orca_log, "AGENT_FAKE_RAM": "10", "AGENT_FAKE_CPU": "10"}
        patch = mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)
        self.start_on()
        self.terr = ac.territory_id(os.path.join(self.repo, ".git"))

    def start_on(self):
        os.makedirs(os.path.dirname(self.start_file), exist_ok=True)
        with open(self.start_file, "w") as fh:
            fh.write(self.fake.host + "\n")
        os.chmod(self.start_file, 0o600)

    def orca_calls(self):
        try:
            with open(self.orca_log) as fh:
                return [json.loads(l) for l in fh if l.strip()]
        except OSError:
            return []

    def creates(self):
        return [a for a in self.orca_calls() if a[:2] == ["terminal", "create"]]

    def last(self, oid_):
        acks = self.fake.order_acks_of(oid_)
        return acks[-1] if acks else None

    def state_of(self, oid_):
        return (self.last(oid_) or {}).get("state")

    def answered(self, oid_, state=None, timeout=15):
        ok = wait_for(lambda: self.state_of(oid_) == state if state else self.last(oid_), timeout=timeout)
        self.assertTrue(ok, "order %s: wanted %s, the acks were %r" % (oid_, state or "an answer", self.fake.order_acks_of(oid_)))
        return self.last(oid_)

    def decisions(self):
        try:
            with open(os.path.join(self.base, "cityhome", "decisions.jsonl"), encoding="utf-8") as fh:
                return [json.loads(l) for l in fh if l.strip()]
        except OSError:
            return []

    def start_bodies(self):
        return [b["talk"]["start"] for b in self.fake.sync_bodies()
                if isinstance(b, dict) and isinstance(b.get("talk"), dict) and "start" in b["talk"]]


class TestOrderComesDown(StartCase):
    OID = "oid-down-00000000001"

    def test_down_to_the_opener_and_the_answer_up(self):
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr, age=2000)
        ack = self.answered(self.OID, "opening")
        self.assertEqual(ack, {"oid": self.OID, "state": "opening", "info": {"name": "shop Manager", "role": "main"}})
        creates = self.creates()
        self.assertEqual(len(creates), 1, "one order = one terminal: %r" % creates)
        self.assertEqual(creates[0], ["terminal", "create", "--worktree", "path:" + self.repo, "--title", "shop Manager",
                                      "--command", ac.agent_command("shop Manager", self.repo, ac.pass_city_dir(self.dir)),
                                      "--json"])
        self.add(sid="new1", ev="UserPromptSubmit", tool="")           # the new session's first line
        ack = self.answered(self.OID, "opened")
        self.assertEqual(ack["info"], {"name": "shop Manager", "role": "main"})
        self.assertEqual(len(self.creates()), 1)
        rows = [r for r in self.decisions() if r.get("verb") == "add-agent"]
        self.assertEqual([(r["outcome"], r["via"], r["oid"], r["repo"]) for r in rows],
                         [(o, "cloud", self.OID, "shop") for o in ("taken", "opening", "opened")])
        self.assertEqual(self.fake.talk_headers()[-1], TALK, "the order rides the talk sync: no new secret, no third path")

    def test_the_new_session_can_be_talked_to_at_once(self):
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        self.answered(self.OID, "opening")
        self.add(sid="new1", ev="UserPromptSubmit", tool="")
        self.answered(self.OID, "opened")
        self.fake.say("cid-after-open-0001", "s:new1", "hello new one")
        self.assertTrue(wait_for(lambda: self.last_ack("cid-after-open-0001"), timeout=10), "G5: step 2's talk reaches it")
        self.assertEqual(self.last_ack("cid-after-open-0001")["state"], "queued")

    def test_the_answer_goes_up_within_two_seconds(self):
        self.up(relay_sec="4")
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        self.answered(self.OID)
        with self.fake.lock:
            syncs = [r for r in self.fake.requests if r["path"] == "/v1/sync"]
        down = [r["t"] for r in syncs if r["status"] == 200 and isinstance(r["body"], dict)]
        acked = [r["t"] for r in syncs
                 if any(a.get("oid") == self.OID
                        for a in (((r["body"] or {}).get("talk") or {}).get("start") or {}).get("acks") or [])]
        before = max(t for t in down if t < acked[0])
        self.assertLess(acked[0] - before, 2.2, "the answer must not wait for the next 4 s sync")

    def test_handed_down_again_and_again_opened_once(self):
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        self.answered(self.OID, "opening")
        for _ in range(3):
            self.fake.order(self.OID, self.terr)
            time.sleep(0.5)
        self.assertEqual(len(self.creates()), 1)
        self.assertEqual({a["state"] for a in self.fake.order_acks_of(self.OID)}, {"opening"})

    def test_every_sync_of_a_start_machine_carries_start(self):
        self.up()
        self.session("tm1")
        self.assertTrue(wait_for(lambda: len(self.start_bodies()) >= 3, timeout=10),
                        "start on: the talk of every sync carries start, so the relay knows this machine takes orders")
        self.assertEqual(self.start_bodies()[-1], {})

    def test_nothing_of_the_order_reaches_orca(self):
        self.up()
        self.session("tm1")
        mark_oid = "oid_" + MARK + "-0000000000003"
        self.fake.order(mark_oid, self.terr, force=True, cmd="touch /tmp/pwned-" + MARK, path="/tmp/" + MARK,
                        folder="/tmp/" + MARK, name="name-" + MARK, title="title-" + MARK, model="model-" + MARK,
                        flags=["--dangerously-skip-permissions", "--" + MARK], command="claude --" + MARK,
                        text="text " + MARK, role="task-manager", worktree="path:/tmp/" + MARK)
        self.answered(mark_oid, "opening")
        calls = self.orca_calls()
        self.assertEqual(len(self.creates()), 1)
        blob = json.dumps(calls)
        for word in (MARK, mark_oid, self.terr, "dangerously", "task-manager"):
            self.assertNotIn(word, blob, "nothing of an order may reach the opener's arguments")
        self.assertEqual(self.creates()[0][3], "path:" + self.repo, "the folder is this machine's own")


class TestOrderRefused(StartCase):
    OID = "oid-refused-00000001"

    def test_a_repo_that_is_not_joined_or_not_here(self):
        other = make_repo(self.base, name="private", origin="git@github.com:Acme/Private.git")
        self.up()
        self.session("tm1")
        self.session("px1", repo=other)
        bad = {"oid-bad-private-00001": ac.territory_id(os.path.join(other, ".git")),   # here, but not joined to this relay
               "oid-bad-unknown-00001": "0badc0de",                                    # no territory of this machine
               "oid-bad-path-00000001": self.repo, "oid-bad-rel-000000001": "../../etc"}
        for oid_, terr in bad.items():
            self.fake.order(oid_, terr)
            self.answered(oid_, "failed")
            self.assertEqual(self.last(oid_).get("why"), "refused", oid_)
        self.assertEqual(self.creates(), [], "a refused order opens nothing")

    def test_start_off_takes_nothing_and_on_works_with_the_next_sync(self):
        os.remove(self.start_file)
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        time.sleep(2.0)
        self.assertEqual(self.fake.order_acks_of(self.OID), [])
        self.assertEqual(self.creates(), [])
        self.assertEqual(self.start_bodies(), [], "start off: the talk carries no start")
        self.assertEqual(self.fake.talk_headers()[-1], TALK, "talk stays on: two switches")
        self.start_on()
        self.answered(self.OID, "opening")
        self.assertEqual(len(self.creates()), 1, "cloud-start on works with the next sync, no restart")

    def test_orders_in_a_reply_are_never_read_with_start_off(self):
        os.remove(self.start_file)
        self.fake.force_start = True                         # a relay that hands orders down although nobody asked
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        self.fake.say("cid-carrier-00000001", "s:tm1", "a message still comes down")
        self.assertTrue(wait_for(lambda: self.last_ack("cid-carrier-00000001"), timeout=10))
        time.sleep(1.0)
        self.assertEqual(self.creates(), [], "the switch on THIS machine decides, never the relay")
        self.assertEqual(self.fake.order_acks_of(self.OID), [])

    def test_talk_off_takes_nothing(self):
        os.remove(self.talk_file)
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        time.sleep(2.0)
        self.assertEqual(self.creates(), [])
        self.assertEqual(set(self.fake.talk_headers()), {None}, "no talk key: no talk, and start needs talk")

    def test_a_line_from_another_member_is_never_an_order(self):
        self.up()
        self.session("tm1")
        forged = hook_line(self.repo, sid="evil", ev="UserPromptSubmit")
        order = {"oid": "oid-forged-000000001", "terr": self.terr, "force": True, "age": 0}
        forged.update({"rid": "github.com/acme/shop", "br": "main", "who": "Mallory", "dev": "dev-evil",
                       "oid": order["oid"], "terr": self.terr, "force": True, "orders": [order],
                       "start": {"state": "on", "orders": [order]}, "talk": {"start": {"state": "on", "orders": [order]}}})
        self.fake.push("dev-evil", forged)
        time.sleep(2.0)
        self.assertEqual(self.creates(), [], "the team key carries events, never an order")
        self.assertEqual(self.fake.order_acks_of(order["oid"]), [])


class TestOrderAnswers(StartCase):
    OID = "oid-answer-000000001"

    def test_over_the_cap_then_the_owners_yes(self):
        with mock.patch.dict(os.environ, {"AGENT_FAKE_RAM": "95", "AGENT_FAKE_CPU": "41"}):
            self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        ack = self.answered(self.OID, "cap")
        self.assertEqual((ack["info"]["ram"], ack["info"]["cpu"]), (95, 41))
        self.assertGreater(ack["info"]["max"], 0)
        self.assertEqual(self.creates(), [])
        self.fake.order("oid-answer-000000002", self.terr, force=True)
        self.answered("oid-answer-000000002", "opening")
        self.assertEqual(len(self.creates()), 1)

    def test_orca_refuses(self):
        with open(self.orca_log + ".mode", "w") as fh:
            fh.write("fail\n")
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        ack = self.answered(self.OID, "failed")
        self.assertEqual(ack.get("why"), "orca")
        detail = ack["info"]["detail"]
        self.assertIn("not signed in", detail)
        self.assertNotIn("/Users/owner/secret", detail)
        self.assertLessEqual(len(detail), 200)

    def test_no_orca_on_this_machine(self):
        with mock.patch.dict(os.environ, {"AGENT_RUNTIME": "plain"}):
            self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        ack = self.answered(self.OID, "failed")
        self.assertEqual(ack, {"oid": self.OID, "state": "failed", "why": "no-orca"})
        self.assertNotIn("claude", json.dumps(self.fake.order_acks), "the command to run by hand never goes up")
        self.assertEqual(self.creates(), [])

    def test_after_a_restart_the_same_order_is_never_opened_again(self):
        proc = self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        self.answered(self.OID, "opening")
        proc.terminate()
        proc.wait(10)
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr)
        ack = self.answered(self.OID, "failed")
        self.assertEqual(ack.get("why"), "restart")
        self.assertEqual(len(self.creates()), 1, "a restart in the middle cannot open two")
        seen = os.path.join(self.dir, "cloud-orders")
        self.assertTrue(os.path.isfile(seen), "<city dir>/cloud-orders")
        self.assertEqual(stat.S_IMODE(os.stat(seen).st_mode), 0o600)

    def test_an_old_order_is_never_opened(self):
        self.up()
        self.session("tm1")
        self.fake.order(self.OID, self.terr, age=400000)     # the machine was away: the relay hands down a late one
        ack = self.answered(self.OID, "failed")
        self.assertEqual(ack.get("why"), "off")
        self.assertEqual(self.creates(), [])


class TestJoinDirServer(StartCase):
    def test_an_order_opens_in_a_repo_joined_from_outside(self):
        os.remove(os.path.join(self.repo, ".secrets", "agent-city-relay"))
        joins = os.path.join(self.base, "joins")
        os.makedirs(joins)
        with open(os.path.join(joins, "shop"), "w") as fh:
            fh.write("address=%s\nkey=%s\n" % (self.fake.url, self.fake.key))
        self.start("--idle-sec", "60", "--relay-sec", "0.2", "--cloud-snap-sec", "60", "--join-dir", joins)
        self.session("tm1")
        self.fake.order("oid-joindir-00000001", self.terr)
        self.answered("oid-joindir-00000001", "opening")
        self.assertEqual(len(self.creates()), 1)
        self.assertEqual(self.creates()[0][3], "path:" + self.repo)


class TestPicture(StartCase):
    def test_the_picture_says_which_repos_are_here(self):
        self.up(snap_sec="0.5")
        self.session("tm1")
        self.assertTrue(wait_for(lambda: (self.last_snap() or {}).get("agents"), timeout=10))
        world = self.last_snap()["world"]
        self.assertEqual([(t["name"], t.get("here")) for t in world["territories"]], [("shop", True)])
        self.assertNotIn(self.base, json.dumps([v for _, v in self.fake.view_log]), "never a path")
        self.assertNotIn('"type": "adding"', json.dumps([v for _, v in self.fake.view_log]),
                         "the state of an order travels in the acks, never in the picture")


class TestStayUp(StartCase):
    def running(self, proc, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if proc.poll() is not None:
                return False
            time.sleep(0.2)
        return True

    def up_slow(self, idle="2", slow="1.5"):
        return self.start("--idle-sec", idle, "--relay-sec", "0.2", "--cloud-snap-sec", "60", "--slow-sec", slow)

    def ended(self):
        """A session came and went: the city knows the repo, nobody lives there now."""
        self.session("tm1")
        self.picture()
        self.add(sid="tm1", ev="SessionEnd", role="task-manager", tool="")

    def test_start_on_keeps_the_server_up_with_nobody_there(self):
        proc = self.up_slow()
        self.ended()
        self.assertTrue(self.running(proc, 7.0),
                        "the server stopped itself: the first agent can no longer be started from the phone")
        self.assertEqual(self.health()["clients"], 0, "no browser was open")
        self.fake.order("oid-nobody-000000001", self.terr)
        self.answered("oid-nobody-000000001", "opening")
        self.assertEqual(self.creates()[0][5], "shop Manager", "nobody there: the new one is the main manager")

    def test_start_off_stops_as_before(self):
        os.remove(self.start_file)
        proc = self.up_slow()
        self.ended()
        self.assertFalse(self.running(proc, 9.0), "start off and nobody there: the idle stop is the one of before")

    def test_start_on_without_talk_stops_as_before(self):
        os.remove(self.talk_file)
        proc = self.up_slow()
        self.ended()
        self.assertFalse(self.running(proc, 9.0), "no talk key: the machine takes no order, nothing to stay up for")

    def test_the_cloud_page_off_stops_as_before(self):
        self.fake.city = False
        proc = self.up_slow()
        self.session("tm1")
        self.add(sid="tm1", ev="SessionEnd", role="task-manager", tool="")
        self.assertFalse(self.running(proc, 9.0))

    def test_with_nobody_there_it_asks_slowly(self):
        proc = self.up_slow(idle="60", slow="1.5")
        self.ended()
        time.sleep(2.0)                                      # the last fast syncs are over
        with self.fake.lock:
            before = len([r for r in self.fake.requests if r["path"] == "/v1/sync"])
        time.sleep(4.0)
        with self.fake.lock:
            got = len([r for r in self.fake.requests if r["path"] == "/v1/sync"]) - before
        self.assertLessEqual(got, 4, "%d syncs in 4 s: with nobody there it asks every slow-sec (1.5 s here), not every 0.2 s" % got)
        self.assertGreaterEqual(got, 1, "it still asks: an order must come down")

    def test_with_a_session_at_work_it_asks_fast(self):
        self.up_slow(idle="60", slow="5")
        self.add(sid="tm1", ev="UserPromptSubmit", role="task-manager", tool="", pid=str(os.getpid()))
        self.picture()
        time.sleep(1.0)
        with self.fake.lock:
            before = len([r for r in self.fake.requests if r["path"] == "/v1/sync"])
        time.sleep(2.0)
        with self.fake.lock:
            got = len([r for r in self.fake.requests if r["path"] == "/v1/sync"]) - before
        self.assertGreaterEqual(got, 4, "a live session: relay-sec as before")


if __name__ == "__main__":
    unittest.main()
