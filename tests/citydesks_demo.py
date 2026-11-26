#!/usr/bin/env python3
"""city-agents-at-desks click path helper (no tests here): start the city of THIS checkout on a free port with temp
dirs, and put real-looking sessions and their agents on floors without a real session, by appending hook lines to
events.jsonl in the exact shape bin/agent-city-hook.sh writes them.

    python3 tests/citydesks_demo.py start  --base DIR [--port P] [--lang zh|en] [--root CHECKOUT]   server up, prints the URL
    python3 tests/citydesks_demo.py team   --base DIR    floor "team-floor": a task manager with 2 workers, a reviewer
                                                          and a merge deputy
    python3 tests/citydesks_demo.py crowd  --base DIR    floor "crowd-floor": 6 task managers x 4 workers = 30 characters
    python3 tests/citydesks_demo.py work   --base DIR [--seconds S]   tool lines for every live agent every 2 s
    python3 tests/citydesks_demo.py stop-one --base DIR   worker 1 of the team stops (SubagentStop)
    python3 tests/citydesks_demo.py end    --base DIR    the team's session ends (SessionEnd): its agents leave too
    python3 tests/citydesks_demo.py phone  --base DIR [--port P]   a page that frames the city at 390x844 (phone width)
                                                          inside a normal browser window; prints PHONE URLs (city, #demo)
    python3 tests/citydesks_demo.py stop   --base DIR    stop the servers, delete DIR

DIR is a fresh temp folder (e.g. $(mktemp -d)); it holds city/ (AGENT_CITY_DIR), home/ (AGENT_CITY_HOME) and repos/.
"""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEAM = "team-floor"
CROWD = "crowd-floor"
TEAM_SID = "demo-team-tm"
TEAM_AGENTS = [  # (aid, agent_type, description)
    ("demo-w1", "auto-pipeline:worker", "city-agents-at-desks Worker 1: seats"),
    ("demo-w2", "auto-pipeline:worker", "city-agents-at-desks Worker 2: plates"),
    ("demo-rv", "auto-pipeline:reviewer", "city-agents-at-desks PR REVIEW"),
    ("demo-md", "auto-pipeline:merge-deputy", "city-agents-at-desks merge"),
]
CROWD_TASKS = ["bank-recon", "stock-lock", "receipt-print", "office-login", "price-check", "sync-report"]
TOOLS = [("Edit", "bin/app.py"), ("Read", ""), ("Bash", ""), ("Write", "docs/notes.md")]


def paths(base):
    base = os.path.abspath(base)
    return {"base": base, "city": os.path.join(base, "city"), "home": os.path.join(base, "home"),
            "repos": os.path.join(base, "repos"), "live": os.path.join(base, "live.json")}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_repo(p, name):
    folder = os.path.join(p["repos"], name)
    if not os.path.isdir(os.path.join(folder, ".git")):
        os.makedirs(folder, exist_ok=True)
        subprocess.run(["git", "init", "-q", folder], check=True)
    return folder


def transcript(p, sid, title):
    """A one-line transcript whose custom title is the session's real name (the server reads it from tp)."""
    folder = os.path.join(p["base"], "transcripts")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, sid + ".jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "custom-title", "customTitle": title, "sessionId": sid}) + "\n")
    return path


def line(p, ev, sid, folder, aid="", at="", tool="", role="", desc="", sub="", file="", tp=""):
    """One hook line, the same keys in the same order as bin/agent-city-hook.sh."""
    repo = os.path.realpath(os.path.join(folder, ".git"))
    obj = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": os.path.basename(folder),
           "role": role, "desc": desc, "sub": sub, "q": "", "klen": "", "repo": repo, "to": "", "ask": "", "wt": "",
           "file": file, "tp": tp, "pid": ""}
    with open(os.path.join(p["city"], "events.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, separators=(",", ":")) + "\n")


def load_live(p):
    try:
        with open(p["live"], encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"sessions": {}, "agents": {}}


def save_live(p, live):
    with open(p["live"], "w", encoding="utf-8") as fh:
        json.dump(live, fh)


def start_session(p, live, sid, folder, title):
    tp = transcript(p, sid, title)
    line(p, "SessionStart", sid, folder, role="task-manager", tp=tp)
    line(p, "UserPromptSubmit", sid, folder, role="task-manager", tp=tp)
    live["sessions"][sid] = {"folder": folder, "tp": tp}


def start_agent(p, live, sid, aid, at, desc):
    s = live["sessions"][sid]
    line(p, "PreToolUse", sid, s["folder"], tool="Agent", role="task-manager", desc=desc, sub=at, tp=s["tp"])
    line(p, "SubagentStart", sid, s["folder"], aid=aid, at=at)
    live["agents"][aid] = {"sid": sid, "at": at}


def cmd_start(p, port, lang, root=ROOT):
    for k in ("city", "home", "repos"):
        os.makedirs(p[k], exist_ok=True)
    start_dir = make_repo(p, TEAM)
    port = port or free_port()
    if port == 4777:
        sys.exit("pick a port other than 4777 (the city of the real sessions)")
    log = open(os.path.join(p["base"], "server.log"), "a")
    proc = subprocess.Popen([sys.executable, os.path.join(root, "bin", "agent_city.py"), "serve", "--dir", p["city"], "--port", str(port), "--idle-min", "60",
                             "--gov-wait-sec", "60", "--decisions", os.path.join(p["home"], "decisions.jsonl"),
                             "--world", os.path.join(p["home"], "world.json"), "--start-dir", start_dir, "--lang", lang],
                            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    on = os.path.join(p["city"], "on")
    for _ in range(100):
        if os.path.exists(on):
            break
        time.sleep(0.1)
    else:
        proc.kill()
        sys.exit("the city did not start; see " + os.path.join(p["base"], "server.log"))
    print("CITY: http://127.0.0.1:%d/   (pid %d, AGENT_CITY_DIR=%s, AGENT_CITY_HOME=%s)" % (port, proc.pid, p["city"], p["home"]))
    print("DEMO: http://127.0.0.1:%d/#demo" % port)


def cmd_team(p):
    live = load_live(p)
    folder = make_repo(p, TEAM)
    start_session(p, live, TEAM_SID, folder, "city-agents-at-desks Task Manager")
    for aid, at, desc in TEAM_AGENTS:
        start_agent(p, live, TEAM_SID, aid, at, desc)
    save_live(p, live)
    print("team: 1 task manager + %d agents on floor %s" % (len(TEAM_AGENTS), TEAM))


def cmd_crowd(p):
    live = load_live(p)
    folder = make_repo(p, CROWD)
    n = 0
    for i, task in enumerate(CROWD_TASKS):
        sid = "demo-crowd-%d" % i
        start_session(p, live, sid, folder, task + " Task Manager")
        n += 1
        for k in range(1, 5):
            start_agent(p, live, sid, "demo-c%d-w%d" % (i, k), "auto-pipeline:worker", "%s Worker %d: slice %d" % (task, k, k))
            n += 1
    save_live(p, live)
    print("crowd: %d characters on floor %s" % (n, CROWD))


def cmd_work(p, seconds):
    end = time.time() + seconds
    k = 0
    while time.time() < end:
        live = load_live(p)
        for aid, a in live["agents"].items():
            s = live["sessions"].get(a["sid"])
            if not s:
                continue
            tool, file = TOOLS[k % len(TOOLS)]
            line(p, "PostToolUse", a["sid"], s["folder"], aid=aid, at=a["at"], tool=tool, file=file)
            k += 1
        for sid, s in live["sessions"].items():
            line(p, "PostToolUse", sid, s["folder"], tool="Read", role="task-manager", tp=s["tp"])
        time.sleep(2)


def cmd_stop_one(p):
    live = load_live(p)
    a = live["agents"].pop("demo-w1", None)
    if a:
        line(p, "SubagentStop", a["sid"], live["sessions"][a["sid"]]["folder"], aid="demo-w1", at=a["at"])
    save_live(p, live)
    print("worker 1 stopped" if a else "worker 1 was not running")


def cmd_end(p):
    live = load_live(p)
    s = live["sessions"].pop(TEAM_SID, None)
    if s:
        line(p, "SessionEnd", TEAM_SID, s["folder"], role="task-manager", tp=s["tp"])
        live["agents"] = {k: v for k, v in live["agents"].items() if v["sid"] != TEAM_SID}
    save_live(p, live)
    print("team session ended" if s else "the team session was not running")


PHONE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>city at %(w)dx%(h)d</title>
<style>
html,body{margin:0;height:100%%;background:#2a2b45;overflow:hidden}
#wrap{position:absolute;left:50%%;top:8px;transform-origin:top center}
#cap{font:600 12px/18px system-ui,sans-serif;color:#fff;text-align:center}
iframe{display:block;width:%(w)dpx;height:%(h)dpx;border:0;background:#fff;box-shadow:0 4px 24px rgba(0,0,0,.4)}
</style></head><body>
<div id="wrap"><div id="cap">%(w)d x %(h)d (shown at <span id="pct">100</span>%%)</div><iframe id="city" src="%(src)s" title="city"></iframe></div>
<script>
// the city lays itself out at exactly %(w)dx%(h)d CSS px inside the frame; the frame is only scaled to fit this window
function fit(){ const s = Math.min(1, (innerHeight - 16) / (%(h)d + 18), (innerWidth - 16) / %(w)d), w = document.getElementById('wrap');
  w.style.transform = 'translateX(-50%%) scale(' + s + ')'; document.getElementById('pct').textContent = Math.round(s * 100); }
addEventListener('resize', fit); fit();
</script></body></html>
"""


def cmd_phone(p, port):
    try:
        with open(os.path.join(p["city"], "on"), encoding="utf-8") as fh:
            city_port = int(fh.read().split()[1])
    except (OSError, ValueError, IndexError):
        sys.exit("start the city first (citydesks_demo.py start)")
    port = port or free_port()
    proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "_phone", "--base", p["base"], "--port", str(port)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    with open(os.path.join(p["base"], "phone.pid"), "w") as fh:
        fh.write(str(proc.pid))
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    print("PHONE: http://127.0.0.1:%d/            (the city at 390x844, city port %d)" % (port, city_port))
    print("PHONE: http://127.0.0.1:%d/?hash=demo  (#demo at 390x844)" % port)


def serve_phone(p, port):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlsplit

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlsplit(self.path).query)
            try:
                with open(os.path.join(p["city"], "on"), encoding="utf-8") as fh:
                    city_port = int(fh.read().split()[1])
            except (OSError, ValueError, IndexError):
                self.send_error(503, "the city is not running")
                return
            num = lambda k, d: int(q[k][0]) if q.get(k, [""])[0].isdigit() else d
            tag = q.get("hash", [""])[0]
            src = "http://127.0.0.1:%d/%s" % (city_port, ("#" + tag) if tag.isalnum() else "")
            body = (PHONE_PAGE % {"w": num("w", 390), "h": num("h", 844), "src": src}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def cmd_stop(p):
    try:
        with open(os.path.join(p["base"], "phone.pid"), encoding="utf-8") as fh:
            os.kill(int(fh.read().strip()), signal.SIGTERM)
        print("stopped the phone page")
    except (OSError, ValueError):
        pass
    on = os.path.join(p["city"], "on")
    try:
        with open(on, encoding="utf-8") as fh:
            pid = int(fh.read().split()[0])
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        print("stopped pid %d" % pid)
    except (OSError, ValueError, IndexError):
        print("no server running")
    if os.path.basename(p["base"]) and os.path.isdir(p["base"]):
        shutil.rmtree(p["base"], ignore_errors=True)
        print("removed " + p["base"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["start", "team", "crowd", "work", "stop-one", "end", "phone", "stop", "_phone"])
    ap.add_argument("--base", required=True)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--root", default=ROOT, help="start: the checkout whose bin/agent_city.py serves (default: this one)")
    a = ap.parse_args()
    p = paths(a.base)
    if a.cmd == "start":
        cmd_start(p, a.port, a.lang, os.path.abspath(a.root))
    elif a.cmd == "team":
        cmd_team(p)
    elif a.cmd == "crowd":
        cmd_crowd(p)
    elif a.cmd == "work":
        cmd_work(p, a.seconds)
    elif a.cmd == "stop-one":
        cmd_stop_one(p)
    elif a.cmd == "end":
        cmd_end(p)
    elif a.cmd == "phone":
        cmd_phone(p, a.port)
    elif a.cmd == "_phone":
        serve_phone(p, a.port)
    else:
        cmd_stop(p)


if __name__ == "__main__":
    main()
