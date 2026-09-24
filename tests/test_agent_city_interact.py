"""Failing tests for the agent city Interaction (requirements/city.md, Interaction).

Approved mock: mock/city-interact-mock.html. Spike (real Claude Code 2.1.281
sessions): a PermissionRequest hook runs while the terminal dialog is shown;
its decision answers AskUserQuestion (behavior allow + updatedInput.answers)
and approves or denies any other tool. The terminal can still answer first.
Owner decision (main manager, 2026-09-24): the governor answers questions
only. Permission requests always go to the owner. Nothing here lets an agent
approve or deny a permission request.

CONTRACT: server additions (bin/agent_city.py serve)

  New flags: --gov-wait-sec N (default 60), --decisions PATH (default
  ~/.claude/agent-city/decisions.jsonl; its folder is created on the first
  write).

  Token: a new random token (>= 32 url-safe characters) at every start, written
  to DIR/token with mode 0600 before DIR/on. The page at / gets it: the page's
  placeholder __CITY_TOKEN__ is replaced with the token (the page carries
  <meta name="city-token" content="__CITY_TOKEN__">).

  Every request (GET / and /api/* included): the Host header must be
  127.0.0.1:<port> or localhost:<port>, else 403. An Origin header, when
  present, must be http://127.0.0.1:<port> or http://localhost:<port>, else
  403. No response ever carries Access-Control-Allow-Origin. OPTIONS: never 2xx.

  /api/*: header X-City-Token must equal the token (compared with
  hmac.compare_digest), else 403. A request refused before its body is read
  closes the connection, so a kept-alive connection never reads a leftover
  body as the next request. POST bodies are
  one JSON object, at most 64 KB (413 over, 400 when not an object). A
  refused request changes nothing.

  Ask = one open question or permission request. At most 50 open (429 over).
  Ask view (SSE 'ask', snapshot 'asks', GET /api/asks):
    {"id", "agent", "label", "task", "repo", "kind": "question"|"permission",
     "phase": "governor"|"owner", "why", "wait", "left", "tool", "what",
     "questions" (question only), "detail" (permission only), "at"}
    agent: the city id of the asker: aid for a subagent, "gov" for the
      governor session, else "s:<sid>". label/task: from the city when it
      knows that agent, else the role (or agent type) given.
    why: "permission" | "no-governor" | "timeout" | "pass" | "" (still with
      the governor). wait: --gov-wait-sec. left: seconds the governor still
      has (0 once with the owner). at: epoch ms.
    what: one line: the command (Bash), file_path (Edit/Write/MultiEdit),
      url (WebFetch), else the first question, else compact JSON of the
      input; at most 200 characters.
    questions: [{"question", "header", "options": [{"label",
      "description"}], "multiSelect"}], texts kept up to 2000 characters.
    detail: {"command", "description", "file_path", "url", "cwd"}, only the
      keys that exist, each up to 2000 characters.

  POST /api/ask {"sid", "aid", "at", "role", "cwd", "repo", "tool", "input"}
    -> 200 {"id", "phase", "why"}. 400 without tool or input object.
    permission (any tool but AskUserQuestion): phase owner, why permission,
      at once. It never goes to a governor.
    question (AskUserQuestion): phase governor when a governor of the same
      repo was seen (a /api/gov/next call) in the last 15 min and the asker
      is not that governor; else phase owner, why no-governor.
    SSE: {"type": "ask", ...view}.
  Governor phase lasts --gov-wait-sec; then phase owner, why timeout.
    SSE: {"type": "ask_phase", "id", "agent", "kind", "phase": "owner",
    "why", "wait", "at"}.
  GET /api/asks -> {"asks": [open views, oldest first]}
  GET /api/wait?id=ID&timeout=S (S at most 30) -> {"state": "open"} after S,
    or at once {"state": "closed", "by", "verb", "text", "answers", "reason"}.
    404 for an unknown id.
  POST /api/decide (the page; Origin header required and must match)
    permission: {"id", "verb": "allow"|"deny", "reason"?} (reason <= 500 chars)
    question:   {"id", "answers": {"<question>": "<text>", ...}}, every
                question answered with non-empty text, else 400
    -> 200 {"ok": true}; 409 {"state": "closed", "by"} when already closed;
    404 unknown id.
  POST /api/closed {"id"} (the ask hook: the terminal took it, or the hook
    gave up) -> 200, closed by terminal, verb closed; 409 when closed.
  Terminal answered first: a PostToolUse line in events.jsonl with the same
    sid, aid and tool as an open ask (and, when the line has klen, the same
    JSON-escaped byte length of the command / file_path / url) closes the
    oldest such ask: by terminal, verb allow (permission) or answer with
    text "" (question).
  GET /api/gov/next?sid=S&repo=R&watcher=W&timeout=T (T at most 30)
    Marks S the governor of R (seen now). Returns the oldest question of repo
    R in phase governor not yet given to S, and marks it given:
    {"state": "ask", "ask": view}; {"state": "none"} after T; {"state":
    "replaced"} for a watcher W that is not the newest for S (a waiting call
    of the old watcher returns that within 2 s).
  POST /api/gov/answer {"id", "texts": [one per question, in order]} -> 200;
    403 for a permission ask; 400 when the count is wrong; 409 closed.
  POST /api/gov/pass {"id"} -> 200: phase owner, why pass. 403 for a
    permission ask; 409 unless in phase governor.
  Closing (any side) -> SSE {"type": "ask_closed", "id", "agent", "kind",
    "tool", "what", "by": "governor"|"owner"|"terminal",
    "verb": "answer"|"allow"|"deny"|"closed", "text", "reason", "at"}.
    text = the answers joined with "；" (question), else "".
  First answer wins: the first close sticks; every later one gets 409.
  decisions.jsonl: one JSON line per close and per pass:
    {"t": local ISO time with offset, "id", "by", "verb" (answer allow deny
     closed pass), "repo", "agent", "task", "tool", "what", "text", "reason"}
  Snapshot: the first /events message also has "asks": [open views].
  /health also has "asks" (open count), "gov_wait_sec", and "governors"
  (repos with a governor seen in the last 15 min).

CONTRACT: the ask hook, python3 bin/agent_city.py ask [--max-wait-sec N]

  hooks.json runs it on PermissionRequest. stdin: the hook JSON. City dir:
  $AGENT_CITY_DIR, default ~/.cache/agent-city. No DIR/on, a dead pid, no
  DIR/token, or no server answering: exit 0 at once, no output (the terminal
  prompt is untouched). Else POST /api/ask (repo = realpath of `git
  rev-parse --git-common-dir` run in the payload's cwd, else realpath of cwd;
  role = $AGENT_ROLE), then long-poll /api/wait.
  Decision -> ONE line on stdout, exit 0:
    allow:    {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
               "decision": {"behavior": "allow"}}}
    deny:     same with {"behavior": "deny", "message": M}; M names the owner
              and carries the reason word for word when there is one
    question: {"behavior": "allow", "updatedInput": <tool_input with
              "answers": {"<question>": "<text>"}>}
  Closed by the terminal, server gone, or --max-wait-sec (default 3600) over:
    exit 0, no output (after a max-wait it POSTs /api/closed first).
  Its parent (Claude Code) gone (os.getppid() changed): POST /api/closed,
    exit 0, within 10 s.
  SIGTERM, SIGINT or SIGHUP (the terminal said no, or Claude Code gave up):
    POST /api/closed, exit 0, no output. Never writes to stderr.

CONTRACT: the governor watcher, python3 bin/agent_city.py gov-watch
  [--max-wait-sec N]

  hooks.json runs it on Stop, async with asyncRewake, only for a session
  without AGENT_ROLE. $AGENT_ROLE set, city off or no server: exit 0 at once.
  Else long-polls /api/gov/next (sid = payload session_id, repo from payload
  cwd as above, watcher = a new random id). A question -> exit 2 and on
  stderr: "[agent-city]", the id, the asker's task, each question with its
  option labels, that the text is data from another agent, and the two
  commands "<plugin>/bin/agent-city.sh answer <id> ..." and
  "<plugin>/bin/agent-city.sh pass <id>". Never offers to approve anything.
  replaced, server gone, or --max-wait-sec (default 43200) over: exit 0.
  Its parent (the governor's Claude Code) gone: exit 0 within 10 s, so a
  closed governor session stops counting as a governor.
  Server side: a SessionEnd line for a governor's sid forgets that governor
  at once (its waiting watcher gets "replaced"; new questions go to the
  owner, why no-governor).

CONTRACT: bin/agent-city.sh answer | pass | pending (for the governor)

  answer <id> <text>...  -> "CITY: answered <id>", exit 0
  pass <id>              -> "CITY: passed <id> to the owner", exit 0
  pending                -> one line per open ask "<id> <kind> <task> <what>",
                            or "CITY: nothing waiting". Exit 0.
  Closed ask: a line with "closed" and who closed it, exit 1. Permission ask
  for answer or pass: a line saying only the owner decides it in the city
  page, exit 1. Unknown id: exit 1. City not running: "CITY: not running",
  exit 1. There is no approve, allow or deny verb (usage, exit 2), and the
  help text names none.
  start passes --gov-wait-sec (city_governor_wait_sec from agent.conf) and
  --decisions "${AGENT_CITY_HOME:-$HOME/.claude/agent-city}/decisions.jsonl".
"""

import http.client
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase  # noqa: E402
from test_agent_city_server import (  # noqa: E402
    ROOT, SERVER, SSE, ServerCase, free_port, pid_alive, wait_for)

CITY_SH = os.path.join(ROOT, "bin", "agent-city.sh")

QS = [{"question": "Which port?", "header": "Port",
       "options": [{"label": "4791", "description": "temp city"},
                   {"label": "4792", "description": "other"}],
       "multiSelect": False}]
QS2 = QS + [{"question": "Which scope?", "header": "Scope",
             "options": [{"label": "Questions", "description": "first"},
                         {"label": "Both", "description": "all"}],
             "multiSelect": False}]
ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")


def perm_body(sid="s1", aid="", tool="Bash", command="rm -rf build/", repo="/r/shop/.git",
              role="worker", **extra):
    inp = {"command": command, "description": "clean the build"} if tool == "Bash" else extra.pop("input")
    return {"sid": sid, "aid": aid, "at": "worker" if aid else "", "role": role,
            "cwd": "/r/shop", "repo": repo, "tool": tool, "input": inp}


def q_body(sid="s2", aid="", questions=None, repo="/r/shop/.git", role="worker"):
    return {"sid": sid, "aid": aid, "at": "worker" if aid else "", "role": role,
            "cwd": "/r/shop", "repo": repo, "tool": "AskUserQuestion",
            "input": {"questions": questions or QS}}


class InteractCase(ServerCase):
    GOV_WAIT = "60"

    def setUp(self):
        super().setUp()
        self.decisions = os.path.join(self.base, "home", "agent-city", "decisions.jsonl")

    def start(self, *extra, wait=True):
        args = list(extra) or ["--idle-sec", "60", "--gov-wait-sec", self.GOV_WAIT,
                               "--decisions", self.decisions]
        return super().start(*args, wait=wait)

    def token(self):
        with open(os.path.join(self.dir, "token")) as fh:
            return fh.read().strip()

    @property
    def origin(self):
        return "http://127.0.0.1:%d" % self.port

    def api(self, method, path, body=None, token=True, origin=None, host=None, raw=None,
            ctype="application/json", timeout=40):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        headers = {}
        if token is True:
            headers["X-City-Token"] = self.token()
        elif token:
            headers["X-City-Token"] = token
        if origin:
            headers["Origin"] = origin
        if host:
            headers["Host"] = host
        data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        if data is not None:
            headers["Content-Type"] = ctype
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        text = resp.read()
        conn.close()
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = text
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, parsed

    def ask(self, body):
        status, _, out = self.api("POST", "/api/ask", body)
        self.assertEqual(status, 200, out)
        return out["id"]

    def asks(self):
        return self.api("GET", "/api/asks")[2]["asks"]

    def view(self, ask_id):
        return next((a for a in self.asks() if a["id"] == ask_id), None)

    def decide(self, body, origin=True):
        return self.api("POST", "/api/decide", body, origin=self.origin if origin is True else origin)

    def gov_next(self, sid="gs", repo="/r/shop/.git", watcher="w1", timeout=0):
        path = "/api/gov/next?sid=%s&repo=%s&watcher=%s&timeout=%s" % (sid, repo, watcher, timeout)
        return self.api("GET", path, timeout=timeout + 20)[2]

    def decisions_lines(self):
        if not os.path.exists(self.decisions):
            return []
        with open(self.decisions) as fh:
            return [json.loads(l) for l in fh if l.strip()]


# ---------------------------------------------------------------------------
# Server: who may talk to it
# ---------------------------------------------------------------------------

class TestToken(InteractCase):
    def test_token_file_private_and_long(self):
        self.start()
        path = os.path.join(self.dir, "token")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertRegex(self.token(), r"^[A-Za-z0-9_\-]{32,}$")

    def test_new_token_every_start(self):
        proc = self.start()
        first = self.token()
        proc.terminate()
        proc.wait(5)
        self.start()
        self.assertNotEqual(self.token(), first)

    def test_page_gets_the_token(self):
        page = os.path.join(self.base, "page.html")
        with open(page, "w") as fh:
            fh.write('<!doctype html><meta name="city-token" content="__CITY_TOKEN__"><p>x</p>')
        self.start("--idle-sec", "60", "--page", page, "--decisions", self.decisions)
        body = self.get("/")[2].decode("utf-8")
        self.assertIn('content="%s"' % self.token(), body)
        self.assertNotIn("__CITY_TOKEN__", body)

    def test_api_needs_the_token(self):
        self.start()
        self.assertEqual(self.api("GET", "/api/asks", token=None)[0], 403)
        self.assertEqual(self.api("GET", "/api/asks", token="wrong" * 8)[0], 403)
        self.assertEqual(self.api("GET", "/api/asks")[0], 200)

    def test_a_refused_request_changes_nothing(self):
        self.start()
        self.assertEqual(self.api("POST", "/api/ask", perm_body(), token=None)[0], 403)
        self.assertEqual(self.asks(), [])


class TestConnection(InteractCase):
    def test_token_compare_is_constant_time(self):
        with open(SERVER) as fh:
            self.assertTrue("hmac.compare_digest" in fh.read(), "use hmac.compare_digest for the token")

    def test_a_refused_body_does_not_spoil_the_next_request(self):
        self.start()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        body = json.dumps(perm_body()).encode("utf-8")
        conn.request("POST", "/api/ask", body=body, headers={"Content-Type": "application/json"})
        first = conn.getresponse()
        first.read()
        self.assertEqual(first.status, 403)
        conn.request("GET", "/api/asks", headers={"X-City-Token": self.token()})
        second = conn.getresponse()
        self.assertEqual(second.status, 200, second.read())
        conn.close()


class TestHostAndOrigin(InteractCase):
    def test_foreign_host_is_refused_even_for_the_page(self):
        self.start()
        status, _, body = self.api("GET", "/", token=None, host="evil.example:%d" % self.port)
        self.assertEqual(status, 403)
        self.assertNotIn(self.token().encode(), body if isinstance(body, bytes) else b"")
        self.assertEqual(self.api("GET", "/api/asks", host="evil.example")[0], 403)

    def test_loopback_hosts_pass(self):
        self.start()
        self.assertEqual(self.api("GET", "/api/asks", host="localhost:%d" % self.port)[0], 200)
        self.assertEqual(self.api("GET", "/api/asks", host="127.0.0.1:%d" % self.port)[0], 200)

    def test_foreign_origin_is_refused_with_a_good_token(self):
        self.start()
        status = self.api("POST", "/api/ask", perm_body(), origin="http://evil.example")[0]
        self.assertEqual(status, 403)
        self.assertEqual(self.asks(), [])

    def test_own_origin_passes(self):
        self.start()
        self.assertEqual(self.api("POST", "/api/ask", perm_body(), origin=self.origin)[0], 200)

    def test_decide_needs_the_page_origin(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.decide({"id": ask_id, "verb": "allow"}, origin=None)[0], 403)
        self.assertEqual(self.decide({"id": ask_id, "verb": "allow"}, origin="http://evil.example")[0], 403)
        self.assertIsNotNone(self.view(ask_id))

    def test_no_cors_header_and_no_preflight(self):
        self.start()
        status, headers, _ = self.api("OPTIONS", "/api/decide", origin="http://evil.example")
        self.assertFalse(200 <= status < 300)
        self.assertNotIn("access-control-allow-origin", headers)
        _, headers, _ = self.api("GET", "/api/asks", origin=self.origin)
        self.assertNotIn("access-control-allow-origin", headers)

    def test_bad_bodies(self):
        self.start()
        self.assertEqual(self.api("POST", "/api/ask", raw=b"[1,2]")[0], 400)
        self.assertEqual(self.api("POST", "/api/ask", raw=b"not json")[0], 400)
        self.assertEqual(self.api("POST", "/api/ask", raw=b'{"a":"' + b"x" * 70000 + b'"}')[0], 413)
        self.assertEqual(self.api("POST", "/api/ask", {"sid": "s1", "input": {}})[0], 400)
        self.assertEqual(self.asks(), [])


# ---------------------------------------------------------------------------
# Server: asks
# ---------------------------------------------------------------------------

class TestPermission(InteractCase):
    def test_goes_to_the_owner_at_once(self):
        self.start()
        sse = self.sse()
        self.gov_next()  # a governor is around: still not its job
        ask_id = self.ask(perm_body())
        v = self.view(ask_id)
        self.assertEqual((v["kind"], v["phase"], v["why"]), ("permission", "owner", "permission"))
        self.assertEqual(v["tool"], "Bash")
        self.assertEqual(v["what"], "rm -rf build/")
        self.assertEqual(v["detail"]["command"], "rm -rf build/")
        self.assertEqual(v["detail"]["description"], "clean the build")
        self.assertEqual(v["detail"]["cwd"], "/r/shop")
        self.assertEqual(v["agent"], "s:s1")
        self.assertTrue(wait_for(lambda: sse.events("ask")))
        self.assertEqual(sse.events("ask")[0]["id"], ask_id)

    def test_never_given_to_the_governor(self):
        self.start()
        self.gov_next()
        self.ask(perm_body())
        self.assertEqual(self.gov_next(timeout=1)["state"], "none")

    def test_owner_allows(self):
        self.start()
        sse = self.sse()
        ask_id = self.ask(perm_body())
        status, _, out = self.decide({"id": ask_id, "verb": "allow"})
        self.assertEqual((status, out), (200, {"ok": True}))
        self.assertIsNone(self.view(ask_id))
        closed = wait_for(lambda: sse.events("ask_closed"))
        self.assertEqual({k: closed[0][k] for k in ("id", "by", "verb", "tool", "what", "kind")},
                         {"id": ask_id, "by": "owner", "verb": "allow", "tool": "Bash",
                          "what": "rm -rf build/", "kind": "permission"})
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual((wait["state"], wait["by"], wait["verb"]), ("closed", "owner", "allow"))

    def test_owner_denies_with_a_reason(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.decide({"id": ask_id, "verb": "deny", "reason": "keep dist/"})[0], 200)
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual((wait["verb"], wait["reason"]), ("deny", "keep dist/"))

    def test_first_answer_wins(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.decide({"id": ask_id, "verb": "deny"})[0], 200)
        status, _, out = self.decide({"id": ask_id, "verb": "allow"})
        self.assertEqual(status, 409)
        self.assertEqual(out["by"], "owner")
        self.assertEqual(self.api("POST", "/api/closed", {"id": ask_id})[0], 409)
        self.assertEqual(len(self.decisions_lines()), 1)
        self.assertEqual(self.decisions_lines()[0]["verb"], "deny")

    def test_bad_decisions(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.decide({"id": ask_id, "verb": "maybe"})[0], 400)
        self.assertEqual(self.decide({"id": ask_id, "verb": "deny", "reason": "x" * 501})[0], 400)
        self.assertEqual(self.decide({"id": "nope", "verb": "allow"})[0], 404)
        self.assertIsNotNone(self.view(ask_id))

    def test_what_for_files_and_urls(self):
        self.start()
        e = self.ask(perm_body(tool="Edit", input={"file_path": "/r/shop/a.py", "old_string": "a",
                                                   "new_string": "b"}))
        w = self.ask(perm_body(tool="WebFetch", input={"url": "https://example.com/x", "prompt": "p"}))
        self.assertEqual(self.view(e)["what"], "/r/shop/a.py")
        self.assertEqual(self.view(e)["detail"]["file_path"], "/r/shop/a.py")
        self.assertEqual(self.view(w)["what"], "https://example.com/x")

    def test_long_texts_are_cut(self):
        self.start()
        ask_id = self.ask(perm_body(command="echo " + "x" * 5000))
        v = self.view(ask_id)
        self.assertLessEqual(len(v["what"]), 200)
        self.assertLessEqual(len(v["detail"]["command"]), 2000)
        self.assertTrue(v["detail"]["command"].startswith("echo xxx"))

    def test_at_most_fifty_open(self):
        self.start()
        for i in range(50):
            self.ask(perm_body(sid="s%d" % i))
        self.assertEqual(self.api("POST", "/api/ask", perm_body(sid="s99"))[0], 429)


class TestQuestion(InteractCase):
    def test_no_governor_goes_to_the_owner(self):
        self.start()
        ask_id = self.ask(q_body())
        v = self.view(ask_id)
        self.assertEqual((v["kind"], v["phase"], v["why"]), ("question", "owner", "no-governor"))
        self.assertEqual(v["questions"], QS)
        self.assertEqual(v["what"], "Which port?")

    def test_governor_of_another_repo_does_not_count(self):
        self.start()
        self.gov_next(repo="/r/other/.git")
        self.assertEqual(self.view(self.ask(q_body()))["phase"], "owner")

    def test_the_governor_asking_goes_to_the_owner(self):
        self.start()
        self.gov_next(sid="gs")
        self.assertEqual(self.view(self.ask(q_body(sid="gs", role="")))["why"], "no-governor")

    def test_governor_gets_it_and_answers(self):
        self.start()
        sse = self.sse()
        self.gov_next()
        ask_id = self.ask(q_body())
        v = self.view(ask_id)
        self.assertEqual((v["phase"], v["why"], v["wait"]), ("governor", "", 60))
        self.assertGreater(v["left"], 50)
        got = self.gov_next(timeout=5)
        self.assertEqual(got["state"], "ask")
        self.assertEqual(got["ask"]["id"], ask_id)
        self.assertEqual(got["ask"]["questions"], QS)
        self.assertEqual(self.gov_next(timeout=1)["state"], "none", "given twice")
        status, _, _ = self.api("POST", "/api/gov/answer", {"id": ask_id, "texts": ["4791"]})
        self.assertEqual(status, 200)
        closed = wait_for(lambda: sse.events("ask_closed"))[0]
        self.assertEqual((closed["by"], closed["verb"], closed["text"]), ("governor", "answer", "4791"))
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual(wait["answers"], {"Which port?": "4791"})
        line = self.decisions_lines()[0]
        self.assertEqual((line["by"], line["verb"], line["text"]), ("governor", "answer", "4791"))

    def test_governor_answer_count_must_match(self):
        self.start()
        self.gov_next()
        ask_id = self.ask(q_body(questions=QS2))
        self.assertEqual(self.api("POST", "/api/gov/answer", {"id": ask_id, "texts": ["4791"]})[0], 400)
        self.assertEqual(self.api("POST", "/api/gov/answer",
                                  {"id": ask_id, "texts": ["4791", "Both"]})[0], 200)
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual(wait["text"], "4791；Both")

    def test_governor_can_pass(self):
        self.start()
        sse = self.sse()
        self.gov_next()
        ask_id = self.ask(q_body())
        self.assertEqual(self.api("POST", "/api/gov/pass", {"id": ask_id})[0], 200)
        v = self.view(ask_id)
        self.assertEqual((v["phase"], v["why"], v["left"]), ("owner", "pass", 0))
        phase = wait_for(lambda: sse.events("ask_phase"))[0]
        self.assertEqual((phase["id"], phase["why"]), (ask_id, "pass"))
        self.assertEqual(self.api("POST", "/api/gov/pass", {"id": ask_id})[0], 409)
        self.assertEqual(self.decisions_lines()[0]["verb"], "pass")

    def test_owner_answers_every_question(self):
        self.start()
        ask_id = self.ask(q_body(questions=QS2))
        self.assertEqual(self.decide({"id": ask_id, "answers": {"Which port?": "4791"}})[0], 400)
        self.assertEqual(self.decide({"id": ask_id, "answers": {"Which port?": "4791",
                                                                "Which scope?": " "}})[0], 400)
        self.assertIsNotNone(self.view(ask_id))
        ok = self.decide({"id": ask_id, "answers": {"Which port?": "4791", "Which scope?": "only questions"}})
        self.assertEqual(ok[0], 200)
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual((wait["by"], wait["verb"]), ("owner", "answer"))
        self.assertEqual(wait["answers"], {"Which port?": "4791", "Which scope?": "only questions"})

    def test_the_owner_may_answer_during_the_governor_time(self):
        self.start()
        self.gov_next()
        ask_id = self.ask(q_body())
        self.assertEqual(self.decide({"id": ask_id, "answers": {"Which port?": "4792"}})[0], 200)
        self.assertEqual(self.api("POST", "/api/gov/answer", {"id": ask_id, "texts": ["4791"]})[0], 409)

    def test_governor_never_touches_a_permission(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.api("POST", "/api/gov/answer", {"id": ask_id, "texts": ["yes"]})[0], 403)
        self.assertEqual(self.api("POST", "/api/gov/pass", {"id": ask_id})[0], 403)
        self.assertIsNotNone(self.view(ask_id))
        self.assertEqual(self.decisions_lines(), [])


class TestGovernorTimeout(InteractCase):
    GOV_WAIT = "1"

    def test_no_answer_in_time_goes_to_the_owner(self):
        self.start()
        sse = self.sse()
        self.gov_next()
        ask_id = self.ask(q_body())
        self.assertEqual(self.view(ask_id)["phase"], "governor")
        phase = wait_for(lambda: sse.events("ask_phase"), timeout=5)
        self.assertTrue(phase, "never left the governor")
        self.assertEqual((phase[0]["id"], phase[0]["phase"], phase[0]["why"], phase[0]["wait"]),
                         (ask_id, "owner", "timeout", 1))
        self.assertEqual(self.view(ask_id)["why"], "timeout")
        self.assertEqual(self.decisions_lines(), [], "a timeout is not a decision")


class TestGovernorGone(InteractCase):
    def test_session_end_forgets_the_governor(self):
        self.start()
        self.gov_next(sid="gs")
        self.assertEqual(self.health()["governors"], 1)
        out = {}
        t = threading.Thread(target=lambda: out.update(r=self.gov_next(sid="gs", timeout=20)))
        t.start()
        time.sleep(0.5)
        self.append(json.dumps({"ev": "SessionEnd", "sid": "gs", "aid": "", "at": "", "tool": "",
                                "nt": "", "proj": "shop", "role": "", "desc": "", "sub": "",
                                "q": "", "klen": ""}) + "\n")
        t.join(5)
        self.assertEqual(out.get("r", {}).get("state"), "replaced")
        self.assertEqual(self.health()["governors"], 0)
        self.assertEqual(self.view(self.ask(q_body()))["why"], "no-governor")


class TestGovernorWatcherSlot(InteractCase):
    def test_a_new_watcher_replaces_the_old_one(self):
        self.start()
        out = {}
        t = threading.Thread(target=lambda: out.update(r=self.gov_next(watcher="old", timeout=20)))
        t.start()
        time.sleep(0.5)
        self.gov_next(watcher="new")
        t.join(5)
        self.assertEqual(out.get("r", {}).get("state"), "replaced")
        self.assertEqual(self.gov_next(watcher="old")["state"], "replaced")


class TestTerminal(InteractCase):
    def event(self, ev="PostToolUse", sid="s1", aid="", tool="Bash", klen=""):
        self.append(json.dumps({"ev": ev, "sid": sid, "aid": aid, "at": "worker" if aid else "",
                                "tool": tool, "nt": "", "proj": "shop", "role": "worker",
                                "desc": "", "sub": "", "q": "", "klen": klen}) + "\n")

    def test_hook_says_closed(self):
        self.start()
        sse = self.sse()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.api("POST", "/api/closed", {"id": ask_id})[0], 200)
        closed = wait_for(lambda: sse.events("ask_closed"))[0]
        self.assertEqual((closed["by"], closed["verb"]), ("terminal", "closed"))
        self.assertEqual(self.decide({"id": ask_id, "verb": "allow"})[0], 409)
        self.assertEqual(self.decisions_lines()[0]["by"], "terminal")

    def test_terminal_approved_first(self):
        self.start()
        sse = self.sse()
        ask_id = self.ask(perm_body(sid="s1", aid="a1"))
        self.event(sid="s1", aid="a1", tool="Bash", klen=str(len("rm -rf build/")))
        closed = wait_for(lambda: sse.events("ask_closed"))
        self.assertTrue(closed, "PostToolUse did not close it")
        self.assertEqual((closed[0]["id"], closed[0]["by"], closed[0]["verb"]), (ask_id, "terminal", "allow"))

    def test_other_command_does_not_close_it(self):
        self.start()
        ask_id = self.ask(perm_body(sid="s1", aid="a1"))
        self.event(sid="s1", aid="a1", tool="Bash", klen="3")
        self.event(sid="s1", aid="a2", tool="Bash", klen=str(len("rm -rf build/")))
        self.event(sid="s1", aid="a1", tool="Edit")
        time.sleep(1.0)
        self.assertIsNotNone(self.view(ask_id))

    def test_escaped_length_is_compared(self):
        self.start()
        cmd = 'echo "hé"'
        ask_id = self.ask(perm_body(sid="s1", command=cmd))
        escaped = json.dumps(cmd, ensure_ascii=False)[1:-1].encode("utf-8")
        self.event(sid="s1", tool="Bash", klen=str(len(escaped)))
        self.assertTrue(wait_for(lambda: self.view(ask_id) is None), "same escaped length did not match")

    def test_terminal_answered_a_question(self):
        self.start()
        sse = self.sse()
        ask_id = self.ask(q_body(sid="s2"))
        self.event(sid="s2", tool="AskUserQuestion")
        closed = wait_for(lambda: sse.events("ask_closed"))
        self.assertTrue(closed)
        self.assertEqual((closed[0]["id"], closed[0]["by"], closed[0]["verb"], closed[0]["text"]),
                         (ask_id, "terminal", "answer", ""))


class TestWaitAndViews(InteractCase):
    def test_wait_open_then_unknown(self):
        self.start()
        ask_id = self.ask(perm_body())
        start = time.monotonic()
        self.assertEqual(self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2], {"state": "open"})
        self.assertGreaterEqual(time.monotonic() - start, 0.8)
        self.assertEqual(self.api("GET", "/api/wait?id=zz&timeout=1")[0], 404)

    def test_wait_returns_as_soon_as_it_is_decided(self):
        self.start()
        ask_id = self.ask(perm_body())
        threading.Timer(0.5, lambda: self.decide({"id": ask_id, "verb": "allow"})).start()
        start = time.monotonic()
        out = self.api("GET", "/api/wait?id=%s&timeout=20" % ask_id)[2]
        self.assertEqual(out["state"], "closed")
        self.assertLess(time.monotonic() - start, 5)

    def test_snapshot_and_health_carry_the_open_asks(self):
        self.start()
        ask_id = self.ask(perm_body())
        sse = self.sse()
        snap = sse.messages[0]
        self.assertEqual(snap["type"], "snapshot")
        self.assertEqual([a["id"] for a in snap["asks"]], [ask_id])
        health = self.health()
        self.assertEqual((health["asks"], health["gov_wait_sec"], health["governors"]), (1, 60, 0))
        self.gov_next()
        self.assertEqual(self.health()["governors"], 1)

    def test_known_agent_gets_its_city_name(self):
        self.start()
        self.append(json.dumps({"ev": "SubagentStart", "sid": "s1", "aid": "a7", "at": "worker",
                                "tool": "", "nt": "", "proj": "shop", "role": "", "desc": "",
                                "sub": "", "q": ""}) + "\n")
        self.assertTrue(wait_for(lambda: self.health()["agents"] == 1))
        v = self.view(self.ask(perm_body(sid="s1", aid="a7")))
        self.assertEqual((v["agent"], v["label"]), ("a7", "worker"))


class TestDecisionsLog(InteractCase):
    def test_every_close_is_one_line(self):
        self.start()
        a = self.ask(perm_body(sid="s1"))
        b = self.ask(q_body(sid="s2"))
        self.decide({"id": a, "verb": "deny", "reason": "no"})
        self.decide({"id": b, "answers": {"Which port?": "4791"}})
        rows = self.decisions_lines()
        self.assertEqual([r["id"] for r in rows], [a, b])
        for row in rows:
            with self.subTest(row=row):
                self.assertEqual(set(row), {"t", "id", "by", "verb", "repo", "agent", "task", "tool",
                                            "what", "text", "reason"})
                self.assertRegex(row["t"], ISO)
                self.assertEqual(row["by"], "owner")
                self.assertEqual(row["repo"], "/r/shop/.git")
        self.assertEqual((rows[0]["verb"], rows[0]["reason"], rows[0]["what"]), ("deny", "no", "rm -rf build/"))
        self.assertEqual((rows[1]["verb"], rows[1]["text"], rows[1]["tool"]), ("answer", "4791", "AskUserQuestion"))

    def test_nothing_written_before_a_decision(self):
        self.start()
        self.ask(perm_body())
        self.assertFalse(os.path.exists(self.decisions))


# ---------------------------------------------------------------------------
# The ask hook
# ---------------------------------------------------------------------------

def hook_payload(cwd, tool="Bash", tool_input=None, sid="sess-9", aid=None):
    data = {"session_id": sid, "transcript_path": "/x/t.jsonl", "cwd": cwd,
            "permission_mode": "default"}
    if aid:
        data["agent_id"] = aid
        data["agent_type"] = "worker"
    data.update({"hook_event_name": "PermissionRequest", "tool_name": tool,
                 "tool_input": tool_input or {"command": "touch a.txt", "description": "make a file"},
                 "permission_suggestions": []})
    return json.dumps(data).encode("utf-8")


class AskHookCase(InteractCase):
    def setUp(self):
        super().setUp()
        self.work = os.path.join(self.base, "work")
        os.makedirs(self.work)
        self.hooks = []

    def tearDown(self):
        for p in self.hooks:
            if p.poll() is None:
                p.kill()
        super().tearDown()

    def hook(self, stdin, *args, env=None):
        full = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_ROLE="worker")
        full.pop("CLAUDE_CODE_REMOTE", None)
        full.update(env or {})
        proc = subprocess.Popen([sys.executable, SERVER, "ask"] + (list(args) or ["--max-wait-sec", "30"]),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=full)
        proc.stdin.write(stdin)
        proc.stdin.close()
        self.hooks.append(proc)
        return proc

    def first_ask(self):
        found = wait_for(lambda: self.asks(), timeout=8)
        self.assertTrue(found, "the hook never filed its ask")
        return found[0]

    def finish(self, proc, timeout=15):
        out = proc.stdout.read()
        err = proc.stderr.read()
        proc.wait(timeout)
        return proc.returncode, out, err


class TestAskHookOff(AskHookCase):
    def test_no_city_no_output_at_once(self):
        start = time.monotonic()
        proc = self.hook(hook_payload(self.work))
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))
        self.assertLess(time.monotonic() - start, 2.0)

    def test_dead_pid(self):
        os.makedirs(self.dir)
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("%d %d\n" % (dead.pid, free_port()))
        with open(os.path.join(self.dir, "token"), "w") as fh:
            fh.write("x" * 40)
        code, out, err = self.finish(self.hook(hook_payload(self.work)))
        self.assertEqual((code, out, err), (0, b"", b""))

    def test_nobody_listening(self):
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("%d %d\n" % (os.getpid(), free_port()))
        with open(os.path.join(self.dir, "token"), "w") as fh:
            fh.write("x" * 40)
        start = time.monotonic()
        code, out, err = self.finish(self.hook(hook_payload(self.work)))
        self.assertEqual((code, out, err), (0, b"", b""))
        self.assertLess(time.monotonic() - start, 3.0)


class TestAskHookOn(AskHookCase):
    def test_owner_allows(self):
        self.start()
        proc = self.hook(hook_payload(self.work))
        ask = self.first_ask()
        self.assertEqual(ask["what"], "touch a.txt")
        self.assertEqual(ask["label"], "worker")
        self.assertEqual(ask["repo"], os.path.realpath(self.work))
        self.decide({"id": ask["id"], "verb": "allow"})
        code, out, err = self.finish(proc)
        self.assertEqual((code, err), (0, b""))
        self.assertEqual(json.loads(out), {"hookSpecificOutput": {
            "hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}})
        self.assertEqual(out.count(b"\n"), 1)

    def test_owner_denies_with_a_reason(self):
        self.start()
        proc = self.hook(hook_payload(self.work))
        self.decide({"id": self.first_ask()["id"], "verb": "deny", "reason": "use tmp/ instead"})
        code, out, _ = self.finish(proc)
        decision = json.loads(out)["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["behavior"], "deny")
        self.assertIn("use tmp/ instead", decision["message"])
        self.assertIn("owner", decision["message"])

    def test_owner_denies_without_a_reason(self):
        self.start()
        proc = self.hook(hook_payload(self.work))
        self.decide({"id": self.first_ask()["id"], "verb": "deny"})
        decision = json.loads(self.finish(proc)[1])["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["behavior"], "deny")
        self.assertIn("owner", decision["message"])

    def test_a_question_gets_its_answers(self):
        self.start()
        proc = self.hook(hook_payload(self.work, tool="AskUserQuestion", tool_input={"questions": QS}))
        ask = self.first_ask()
        self.assertEqual(ask["kind"], "question")
        self.decide({"id": ask["id"], "answers": {"Which port?": "4791, but only today"}})
        decision = json.loads(self.finish(proc)[1])["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["behavior"], "allow")
        self.assertEqual(decision["updatedInput"], {"questions": QS,
                                                    "answers": {"Which port?": "4791, but only today"}})

    def test_the_governor_answer_reaches_it(self):
        self.start()
        self.gov_next(repo=os.path.realpath(self.work))
        proc = self.hook(hook_payload(self.work, tool="AskUserQuestion", tool_input={"questions": QS}))
        ask = self.first_ask()
        self.assertEqual(ask["phase"], "governor")
        self.api("POST", "/api/gov/answer", {"id": ask["id"], "texts": ["4791"]})
        decision = json.loads(self.finish(proc)[1])["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["updatedInput"]["answers"], {"Which port?": "4791"})

    def test_subagent_ask_names_the_subagent(self):
        self.start()
        self.hook(hook_payload(self.work, aid="a3"))
        self.assertEqual(self.first_ask()["agent"], "a3")

    def test_repo_is_the_git_common_dir(self):
        main = os.path.join(self.base, "main")
        os.makedirs(main)
        git = ["git", "-C", main, "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "x"], check=True)
        tree = os.path.join(self.base, "tree")
        subprocess.run(git + ["worktree", "add", "-q", tree], check=True)
        self.start()
        self.hook(hook_payload(tree))
        self.assertEqual(self.first_ask()["repo"], os.path.realpath(os.path.join(main, ".git")))

    def test_terminal_first_ends_it_quietly(self):
        self.start()
        proc = self.hook(hook_payload(self.work))
        self.api("POST", "/api/closed", {"id": self.first_ask()["id"]})
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))

    def test_sigterm_closes_it_in_the_city(self):
        self.start()
        sse = self.sse()
        proc = self.hook(hook_payload(self.work))
        ask_id = self.first_ask()["id"]
        proc.send_signal(signal.SIGTERM)
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))
        closed = wait_for(lambda: sse.events("ask_closed"))
        self.assertTrue(closed, "the city never heard the terminal took it")
        self.assertEqual((closed[0]["id"], closed[0]["by"], closed[0]["verb"]), (ask_id, "terminal", "closed"))

    def test_server_gone_ends_it_quietly(self):
        proc_srv = self.start()
        proc = self.hook(hook_payload(self.work))
        self.first_ask()
        proc_srv.terminate()
        start = time.monotonic()
        code, out, _ = self.finish(proc)
        self.assertEqual((code, out), (0, b""))
        self.assertLess(time.monotonic() - start, 10)

    def test_parent_gone_closes_it(self):
        self.start()
        sse = self.sse()
        env = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_ROLE="worker")
        stdin_file = os.path.join(self.base, "req.json")
        with open(stdin_file, "wb") as fh:
            fh.write(hook_payload(self.work))
        # a parent that starts the hook and goes away, like a closed Claude Code
        parent = subprocess.Popen(["sh", "-c", '"$0" "$1" ask --max-wait-sec 60 <"$2" >/dev/null 2>&1 & sleep 1',
                                   sys.executable, SERVER, stdin_file], env=env)
        ask_id = self.first_ask()["id"]
        parent.wait(10)
        closed = wait_for(lambda: sse.events("ask_closed"), timeout=12)
        self.assertTrue(closed, "the hook outlived its parent")
        self.assertEqual((closed[0]["id"], closed[0]["by"], closed[0]["verb"]), (ask_id, "terminal", "closed"))

    def test_max_wait_gives_up_and_closes(self):
        self.start()
        proc = self.hook(hook_payload(self.work), "--max-wait-sec", "2")
        ask_id = self.first_ask()["id"]
        code, out, _ = self.finish(proc)
        self.assertEqual((code, out), (0, b""))
        self.assertIsNone(self.view(ask_id))


# ---------------------------------------------------------------------------
# The governor watcher
# ---------------------------------------------------------------------------

def stop_payload(cwd, sid="gov-1"):
    return json.dumps({"session_id": sid, "transcript_path": "/x/t.jsonl", "cwd": cwd,
                       "permission_mode": "auto", "hook_event_name": "Stop",
                       "stop_hook_active": False}).encode("utf-8")


class TestGovWatch(AskHookCase):
    def watch(self, sid="gov-1", role=None, max_wait="20", cwd=None):
        env = dict(os.environ, AGENT_CITY_DIR=self.dir)
        env.pop("AGENT_ROLE", None)
        if role:
            env["AGENT_ROLE"] = role
        proc = subprocess.Popen([sys.executable, SERVER, "gov-watch", "--max-wait-sec", max_wait],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env)
        proc.stdin.write(stop_payload(cwd or self.work, sid))
        proc.stdin.close()
        self.hooks.append(proc)
        return proc

    def test_citizen_or_city_off_exits_at_once(self):
        code, out, err = self.finish(self.watch())
        self.assertEqual((code, out, err), (0, b"", b""))
        self.start()
        code, out, _ = self.finish(self.watch(role="worker"))
        self.assertEqual((code, out), (0, b""))

    def test_a_question_wakes_the_governor(self):
        self.start()
        proc = self.watch()
        self.assertTrue(wait_for(lambda: self.health()["governors"] == 1, timeout=5),
                        "the watcher never showed up as the governor")
        self.assertEqual(self.view(self.ask(q_body(repo=os.path.realpath(self.work))))["phase"], "governor")
        code, out, err = self.finish(proc)
        text = err.decode("utf-8")
        ask_id = self.asks()[0]["id"]
        self.assertEqual((code, out), (2, b""))
        self.assertIn("[agent-city]", text)
        self.assertIn(ask_id, text)
        self.assertIn("Which port?", text)
        self.assertIn("4791", text)
        self.assertIn("4792", text)
        self.assertIn("data", text)
        city_sh = os.path.join(ROOT, "bin", "agent-city.sh")
        self.assertIn("%s answer %s" % (city_sh, ask_id), text)
        self.assertIn("%s pass %s" % (city_sh, ask_id), text)
        self.assertNotIn("approve", text.lower())

    def test_permissions_never_wake_it(self):
        self.start()
        proc = self.watch(max_wait="3")
        time.sleep(0.5)
        self.ask(perm_body(repo=os.path.realpath(self.work)))
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))

    def test_other_repo_questions_do_not_wake_it(self):
        self.start()
        proc = self.watch(max_wait="3")
        time.sleep(0.5)
        self.ask(q_body(repo="/r/elsewhere/.git"))
        self.assertEqual(self.finish(proc)[0], 0)

    def test_second_watcher_replaces_the_first(self):
        self.start()
        first = self.watch()
        time.sleep(1.0)
        second = self.watch()
        code, _, _ = self.finish(first, timeout=10)
        self.assertEqual(code, 0)
        self.assertIsNone(second.poll())

    def test_parent_gone_ends_the_watcher(self):
        self.start()
        env = dict(os.environ, AGENT_CITY_DIR=self.dir)
        env.pop("AGENT_ROLE", None)
        stdin_file = os.path.join(self.base, "stop.json")
        with open(stdin_file, "wb") as fh:
            fh.write(stop_payload(self.work, sid="gone-gov"))
        pid_file = os.path.join(self.base, "watcher.pid")
        parent = subprocess.Popen(["sh", "-c", '"$0" "$1" gov-watch --max-wait-sec 120 <"$2" >/dev/null 2>&1 & echo $! >"$3"; sleep 1',
                                   sys.executable, SERVER, stdin_file, pid_file], env=env)
        parent.wait(10)
        with open(pid_file) as fh:
            watcher_pid = int(fh.read())
        self.assertTrue(wait_for(lambda: not pid_alive(watcher_pid), timeout=12),
                        "the watcher outlived the governor session")

    def test_server_gone(self):
        srv = self.start()
        proc = self.watch()
        time.sleep(0.5)
        srv.terminate()
        self.assertEqual(self.finish(proc)[0], 0)


# ---------------------------------------------------------------------------
# bin/agent-city.sh for the governor
# ---------------------------------------------------------------------------

class TestCityScriptVerbs(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "city")
        self.home = os.path.join(self.repo.base, "cityhome")
        self.port = free_port()
        self.repo.set_conf("city_port", str(self.port))
        self.repo.set_conf("city_governor_wait_sec", "7")

    def tearDown(self):
        on = os.path.join(self.city, "on")
        if os.path.exists(on):
            try:
                with open(on) as fh:
                    os.kill(int(fh.read().split()[0]), signal.SIGTERM)
            except (OSError, ValueError, IndexError):
                pass
        super().tearDown()

    def city_run(self, *args):
        return self.repo.run("agent-city.sh", *args,
                             env={"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home}, timeout=30)

    def api(self, method, path, body=None):
        with open(os.path.join(self.city, "token")) as fh:
            token = fh.read().strip()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {"X-City-Token": token}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        out = json.loads(resp.read())
        conn.close()
        return resp.status, out

    def started(self):
        result = self.city_run("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_start_passes_the_wait_and_the_log_path(self):
        self.started()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/health")
        self.assertEqual(json.loads(conn.getresponse().read())["gov_wait_sec"], 7)
        conn.close()
        ask_id = self.api("POST", "/api/ask", q_body())[1]["id"]
        self.assertEqual(self.city_run("answer", ask_id, "4791").returncode, 0)
        with open(os.path.join(self.home, "decisions.jsonl")) as fh:
            self.assertEqual(json.loads(fh.readline())["by"], "governor")

    def test_answer(self):
        self.started()
        ask_id = self.api("POST", "/api/ask", q_body(questions=QS2))[1]["id"]
        result = self.city_run("answer", ask_id, "4791", "only questions")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CITY: answered %s" % ask_id, result.stdout)
        again = self.city_run("answer", ask_id, "4792", "x")
        self.assertEqual(again.returncode, 1)
        self.assertIn("closed", again.stdout)
        self.assertIn("governor", again.stdout)

    def test_pass(self):
        self.started()
        self.api("GET", "/api/gov/next?sid=g&repo=/r/shop/.git&watcher=w&timeout=0")
        ask_id = self.api("POST", "/api/ask", q_body())[1]["id"]
        result = self.city_run("pass", ask_id)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CITY: passed %s to the owner" % ask_id, result.stdout)
        self.assertEqual(self.api("GET", "/api/asks")[1]["asks"][0]["why"], "pass")

    def test_permissions_are_the_owners(self):
        self.started()
        ask_id = self.api("POST", "/api/ask", perm_body())[1]["id"]
        for verb in (["answer", ask_id, "yes"], ["pass", ask_id]):
            with self.subTest(verb=verb[0]):
                result = self.city_run(*verb)
                self.assertEqual(result.returncode, 1)
                self.assertIn("owner", result.stdout)
        self.assertEqual(len(self.api("GET", "/api/asks")[1]["asks"]), 1)

    def test_pending(self):
        self.started()
        self.assertIn("CITY: nothing waiting", self.city_run("pending").stdout)
        ask_id = self.api("POST", "/api/ask", perm_body())[1]["id"]
        out = self.city_run("pending").stdout
        self.assertIn(ask_id, out)
        self.assertIn("permission", out)
        self.assertIn("rm -rf build/", out)

    def test_unknown_id_and_not_running(self):
        result = self.city_run("answer", "a1", "x")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CITY: not running", result.stdout)
        self.started()
        self.assertEqual(self.city_run("answer", "nope", "x").returncode, 1)

    def test_no_verb_approves(self):
        self.started()
        ask_id = self.api("POST", "/api/ask", perm_body())[1]["id"]
        for verb in ("approve", "allow", "deny"):
            with self.subTest(verb=verb):
                self.assertEqual(self.city_run(verb, ask_id).returncode, 2)
        help_text = self.city_run("-h").stdout.lower()
        for word in ("approve", "allow", "deny"):
            self.assertNotIn(word, help_text)
        self.assertEqual(len(self.api("GET", "/api/asks")[1]["asks"]), 1)


if __name__ == "__main__":
    unittest.main()
