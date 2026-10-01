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
"""

import json
import os
import subprocess

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

RELAY_ENV = {"TEAM_KEY": KEY, "CITY_USER": ME}
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


def sync(dev, lines=(), after=0, now=T0, key=KEY, view=None):
    body = {"dev": dev, "after": after, "lines": list(lines)}
    if view is not None:
        body["view"] = view
    return {"to": "relay", "method": "POST", "path": "/v1/sync",
            "headers": {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            "body": body, "now": now}


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


def feed(login=ME, dev=None, gen=None, after=None, now=T0):
    args = []
    if dev is not None:
        args.append("dev=%s" % dev)
    if gen is not None:
        args.append("gen=%d" % gen)
    if after is not None:
        args.append("after=%d" % after)
    return get("/api/feed" + ("?" + "&".join(args) if args else ""), login=login, now=now)
