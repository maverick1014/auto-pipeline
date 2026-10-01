"""Shared helpers for the cloud city tests (cloud-city-1).

    RELAY, CITY        the two Worker files (bin/agent-city-relay.js,
                       bin/agent-city-cloud.js)
    run_cloud(case, requests, relay_env=None, city_env=None, assets=None,
              relay=RELAY, city=CITY)
                       runs tests/cloud_harness.mjs, returns its parsed output
    sync(dev, lines=(), after=0, now=T0, key=KEY, view=None)   a relay request
    view(gen, snap=None, events=None, label="mac", counts=None) a view body
    feed(login=ME, dev=None, gen=None, after=None, now=T0)      a city request
    get(path, login=ME, now=T0, method="GET")                   a city request
    snapshot(*people, terr="t1", name="shop")   a small page snapshot message
    person(pid, label, **more)                  a snapshot person
    ME, OTHER          two users (e-mails)
    RELAY_ENV, CITY_ENV  the env each Worker gets in a normal test

cloud-city-2 (talk):
    TALK               the talk key of the tests (never a real one)
    TALK_ENV           RELAY_ENV plus TALK_KEY
    sync(..., talk=None, talk_key=None)   talk_key -> the header X-City-Talk;
                       talk (a dict) -> the body key "talk"
    sql(text, *args)   a statement run straight on the stand-in database
    lay_msg(cid, dev="mac", to="s:tm1", text="hello", at=T0, state="sent", why="", user=ME)
                       one city_msg row, laid with sql()
    send(dev, to, text, cid, login=ME, now=T0, origin=ORIGIN, page="1", ctype=..., body=None)
                       a POST /api/chat/send to the City Worker
    feed(..., chat=None, cc=None)   the feed with an open window
    ORIGIN             the page's own origin in the harness (https://cloud.test)
    MSG_SQL, CHAT_SQL  the two tables, as BOTH Workers must make them (one line each)

cloud-city-3 (start an agent):
    ORDER_SQL, ORDER_INDEX_SQL, START_TABLES   the order table, as BOTH Workers must make it
    make_order_table() the order table, laid with sql()
    lay_order(oid, dev="mac", terr=TERR, force=0, at=T0, ts=None, state="sent", why="", info="{}", user=ME)
                       one city_order row, laid with sql()
    add(dev, terr, oid, force=None, login=ME, now=T0, origin=ORIGIN, page="1", ctype=..., body=None)
                       a POST /api/agent/add to the City Worker
    TERR               a territory id (8 lowercase hex digits)
"""

import json
import os
import subprocess
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
RELAY = os.path.join(BIN, "agent-city-relay.js")
CITY = os.path.join(BIN, "agent-city-cloud.js")
HARNESS = os.path.join(HERE, "cloud_harness.mjs")

from nodehelp import NODE  # noqa: E402

KEY = "test-team-key-not-real-0001"
T0 = 1_800_000_000_000  # a fixed clock, ms
ME = "owner@example.com"
OTHER = "other@example.com"
AUD = "test-aud-0001"       # the harness signs tokens for this audience
TEAM = "testteam"           # ... and this Access team

TALK = "test-talk-key-not-real-0002"
ORIGIN = "https://cloud.test"

RELAY_ENV = {"TEAM_KEY": KEY, "CITY_USER": ME}
TALK_ENV = {"TEAM_KEY": KEY, "CITY_USER": ME, "TALK_KEY": TALK}

# cloud-city-2: the two talk tables. Both Workers run exactly these lines (CREATE ... IF NOT
# EXISTS), so either one may be the first to need them.
MSG_SQL = ("CREATE TABLE IF NOT EXISTS city_msg (user TEXT NOT NULL, cid TEXT NOT NULL, dev TEXT NOT NULL, "
           "pg TEXT NOT NULL, text TEXT NOT NULL, at INTEGER NOT NULL, state TEXT NOT NULL, why TEXT NOT NULL, "
           "PRIMARY KEY (user, cid))")
MSG_INDEX_SQL = "CREATE INDEX IF NOT EXISTS city_msg_dev ON city_msg (user, dev, state)"
CHAT_SQL = ("CREATE TABLE IF NOT EXISTS city_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT NOT NULL, "
            "dev TEXT NOT NULL, pg TEXT NOT NULL, k TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, "
            "at REAL NOT NULL, ts INTEGER NOT NULL, state TEXT NOT NULL, why TEXT NOT NULL, cid TEXT NOT NULL, "
            "UNIQUE (user, dev, k))")
CHAT_INDEX_SQL = "CREATE INDEX IF NOT EXISTS city_chat_pg ON city_chat (user, dev, pg, id)"
TALK_TABLES = (MSG_SQL, MSG_INDEX_SQL, CHAT_SQL, CHAT_INDEX_SQL)

# cloud-city-3: the order table. One row = one click on the cloud page's add-agent button.
# at = when it was placed, ts = when its state last changed (both the Worker's clock, ms),
# info = a small JSON object as text ("{}" when there is nothing to say).
ORDER_SQL = ("CREATE TABLE IF NOT EXISTS city_order (user TEXT NOT NULL, oid TEXT NOT NULL, dev TEXT NOT NULL, "
             "terr TEXT NOT NULL, force INTEGER NOT NULL, at INTEGER NOT NULL, ts INTEGER NOT NULL, "
             "state TEXT NOT NULL, why TEXT NOT NULL, info TEXT NOT NULL, PRIMARY KEY (user, oid))")
ORDER_INDEX_SQL = "CREATE INDEX IF NOT EXISTS city_order_dev ON city_order (user, dev, state)"
START_TABLES = (ORDER_SQL, ORDER_INDEX_SQL)
TERR = "0a1b2c3d"
CITY_ENV = {"ACCESS_TEAM": TEAM, "ACCESS_AUD": AUD}

PAGE = ("<!doctype html><html><head><meta name=\"city-token\" content=\"__CITY_TOKEN__\">"
        "<script src=\"assets/vendor/three.min.js?v=__CITY_ASSET_V__\"></script></head><body>"
        "<script>const LANG = '__CITY_LANG__'; const CLOUD = '__CITY_CLOUD__' === '1';"
        "</script>Agent City</body></html>")
ASSETS = {"/index.html": PAGE,
          "/assets/vendor/three.min.js": "/* three */",
          "/assets/characters/character-male-a.glb": "glb-bytes"}


def run_cloud(case, requests, relay_env=None, city_env=None, assets=None,
              relay=RELAY, city=CITY, check=True):
    for path in (relay, city):
        if path != "-":
            case.assertTrue(os.path.isfile(path), "%s is missing" % os.path.relpath(path, ROOT))
    payload = {"env": {"relay": RELAY_ENV if relay_env is None else relay_env,
                       "city": CITY_ENV if city_env is None else city_env},
               "assets": ASSETS if assets is None else assets,
               "requests": requests}
    proc = subprocess.run([NODE, HARNESS, relay, city, "run"], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=90)
    case.assertEqual(proc.returncode, 0, proc.stderr)
    out = json.loads(proc.stdout)
    if check:
        for r in out["responses"]:
            case.assertNotEqual(r["status"], -1, "a Worker threw: %s" % r["body"])
    return out


def sync(dev, lines=(), after=0, now=T0, key=KEY, view=None, talk=None, talk_key=None):
    body = {"dev": dev, "after": after, "lines": list(lines)}
    if view is not None:
        body["view"] = view
    if talk is not None:
        body["talk"] = talk
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if talk_key is not None:
        headers["X-City-Talk"] = talk_key
    return {"to": "relay", "method": "POST", "path": "/v1/sync", "headers": headers, "body": body, "now": now}


def sql(text, *args):
    return {"to": "sql", "sql": text, "args": list(args)}


def make_tables():
    """The talk tables, laid by the test itself (so a test of one Worker does not need the other)."""
    return [sql(line) for line in TALK_TABLES]


def make_order_table():
    """cloud-city-3: the order table, laid by the test itself."""
    return [sql(line) for line in START_TABLES]


def lay_order(oid, dev="mac", terr=TERR, force=0, at=T0, ts=None, state="sent", why="", info="{}", user=ME):
    return sql("INSERT INTO city_order (user, oid, dev, terr, force, at, ts, state, why, info) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", user, oid, dev, terr, force, at, at if ts is None else ts,
               state, why, info)


def add(dev="mac", terr=TERR, oid="oid-0000000000000001", force=None, login=ME, now=T0,
        origin=ORIGIN, page="1", ctype="application/json", body=None):
    """cloud-city-3: the page's POST /api/agent/add (force is left out of the body when None)."""
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    if page is not None:
        headers["X-City-Page"] = page
    if ctype is not None:
        headers["Content-Type"] = ctype
    req = get("/api/agent/add", login=login, now=now, method="POST", headers=headers)
    if body is None:
        body = {"dev": dev, "terr": terr, "oid": oid}
        if force is not None:
            body["force"] = force
    req["body"] = body
    return req


def lay_msg(cid, dev="mac", to="s:tm1", text="hello", at=T0, state="sent", why="", user=ME):
    return sql("INSERT INTO city_msg (user, cid, dev, pg, text, at, state, why) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               user, cid, dev, to, text, at, state, why)


def lay_chat(k, dev="mac", to="s:tm1", kind="reply", text="hi", at=1.0, ts=T0, state="", why="", cid="", user=ME):
    return sql("INSERT INTO city_chat (user, dev, pg, k, kind, text, at, ts, state, why, cid) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", user, dev, to, k, kind, text, at, ts, state, why, cid)


def send(dev="mac", to="s:tm1", text="hello", cid="cid-0000000000000001", login=ME, now=T0,
         origin=ORIGIN, page="1", ctype="application/json", body=None):
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    if page is not None:
        headers["X-City-Page"] = page
    if ctype is not None:
        headers["Content-Type"] = ctype
    req = get("/api/chat/send", login=login, now=now, method="POST", headers=headers)
    req["body"] = {"dev": dev, "to": to, "text": text, "cid": cid} if body is None else body
    return req


def view(gen, snap=None, events=None, label="mac", counts=None):
    out = {"label": label, "gen": gen,
           "counts": counts if counts is not None else {"people": 1, "busy": 1, "wait": 0}}
    if snap is not None:
        out["snap"] = snap
    if events is not None:
        out["events"] = events
    return out


def person(pid, label, **more):
    out = {"id": pid, "role": "task-manager", "label": label, "task": "", "stuck": False,
           "waiting": False, "done": False, "status": "", "tools": {}, "terr": "t1",
           "relay": None, "lead": "", "office": None}
    out.update(more)
    return out


def snapshot(*people, terr="t1", name="shop"):
    return {"type": "snapshot", "gov": {"state": "idle", "terr": terr}, "govs": [],
            "agents": list(people), "asks": [], "governors": 0, "shows": [],
            "world": {"cell": 2, "x0": 0, "z0": 0, "w": 4, "h": 4, "rows": ["gggg"] * 4,
                      "territories": [{"id": terr, "name": name, "buildings": [], "sites": []}],
                      "links": []}}


def tool(pid, name="Bash"):
    return {"type": "tool", "id": pid, "tool": name, "name": name}


def get(path, login=ME, now=T0, method="GET", headers=None):
    req = {"to": "city", "method": method, "path": path, "now": now,
           "headers": dict(headers or {})}
    if isinstance(login, str):
        req["login"] = {"email": login}
    elif login is not None:
        req["login"] = login
    return req


def feed(login=ME, dev=None, gen=None, after=None, now=T0, chat=None, cc=None):
    args = []
    if dev is not None:
        args.append("dev=%s" % dev)
    if gen is not None:
        args.append("gen=%d" % gen)
    if after is not None:
        args.append("after=%d" % after)
    if chat is not None:
        args.append("chat=%s" % quote(chat, safe=""))
    if cc is not None:
        args.append("cc=%d" % cc)
    return get("/api/feed" + ("?" + "&".join(args) if args else ""), login=login, now=now)
