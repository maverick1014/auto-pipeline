#!/usr/bin/env python3
"""board-trust dry-run: replay this machine's real launches through bin/agent-guard.sh. Read only.

Not a unit test (no test_ prefix). Run by hand before a merge, on each machine that runs managers:

    python3 tests/dryrun_board_trust.py [--since 2026-11-20] [--switch on] [--repo auto-pipeline] [--main <main checkout>]
                                        [--workspaces <folder of the task worktrees>] [--projects <glob>]

What it does, and never more:
- reads every Agent/Task tool call and every Bash call with `orca terminal|worktree` from the transcripts
  (~/.claude/projects/*<repo>*), copied into a temp folder first; request blobs and repeats are skipped
- per launch: a temp git repo with agent.conf and a todo holding the tasks open on that day (the main
  checkout's agent_todo.txt plus agent_completed.txt done on that day or later: lenient, no done time),
  the role from the session folder (main checkout -> main manager, a task worktree -> task manager, a
  call from inside a subagent or anything else -> free)
- pipes PreToolUse, then PostToolUse with the real tool result, then SubagentStop (async agents) through
  the hook of this checkout, with CLAUDE_CONFIG_DIR = a temp dir and a stub `orca` that always fails
- the switch: the main checkout's own agent.conf (auto-pipeline: board_guard=on), else the template
- prints allowed / blocked / recorded / not recorded (split by why: an orca call that is not a pane
  create, such as terminal read/send/wait/list/close or worktree ps/rm, a checked-only worktree create,
  or an agent), loud allows, every block with its line, and whether each linked record was gone at the
  end; deletes the temp folder

It never writes outside its temp folder, never touches ~/.claude or a real repo.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "bin", "agent-guard.sh")
ORCA_RE = re.compile(r"orca\s+(terminal|worktree)")
LIVE = os.getpid()
SWITCH = ""  # --switch: board_guard for the replay (before a merge the main checkout has no board_guard line)


def main_worktree(path):
    r = subprocess.run(["git", "-C", path, "worktree", "list", "--porcelain"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):]
    return path


def tool_uses(path):
    uses, results, seen = [], {}, set()
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return uses, results
    with fh:
        for line in fh:
            if '"tool_use"' not in line and "toolUseResult" not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") if isinstance(d.get("message"), dict) else {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_result" and d.get("toolUseResult") is not None:
                    results[c.get("tool_use_id")] = d["toolUseResult"]
                if c.get("type") != "tool_use" or d.get("type") != "assistant" or c.get("id") in seen:
                    continue
                seen.add(c.get("id"))
                name, inp = c.get("name"), c.get("input") or {}
                if name in ("Agent", "Task") or (name == "Bash" and ORCA_RE.search(inp.get("command", "") or "")):
                    uses.append((d, c))
    return uses, results


def local_now(ts):
    try:
        t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except ValueError:
        t = datetime.datetime.now()
    return t.strftime("%Y-%m-%d %H:%M")


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def todo_names(main):
    current = [l.split(" | ")[0].strip() for l in read(os.path.join(main, "agent_todo.txt")).splitlines()
               if " | " in l]
    done = {}
    for l in read(os.path.join(main, "agent_completed.txt")).splitlines():
        p = l.split(" | ")
        if len(p) > 2 and re.match(r"\d{4}-\d\d-\d\d", p[0]):
            done[p[1].strip()] = p[0][:10]
    return current, done


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(base, repo, open_tasks, role, own, conf):
    main = os.path.join(base, repo)
    os.makedirs(main)
    git("init", "-q", "-b", "main", cwd=main)
    git("-c", "user.email=d@d", "-c", "user.name=d", "commit", "-q", "--allow-empty", "-m", "seed", cwd=main)
    shutil.copy(conf, os.path.join(main, "agent.conf"))
    if SWITCH:
        with open(os.path.join(main, "agent.conf"), "a") as fh:
            fh.write("\nboard_guard=%s\n" % SWITCH)
    with open(os.path.join(main, "agent_todo.txt"), "w") as fh:
        fh.write("".join("%s | big | the %s task | est 60m | opened 2026-01-01 00:00 | by main\n" % (n, n)
                         for n in open_tasks))
    if role == "main":
        with open(os.path.join(main, ".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-01-01 00:00 s-dry term_dry\n" % LIVE)
    if role == "tm":
        wt = os.path.join(base, own)
        git("worktree", "add", "-q", "-b", own, wt, cwd=main)
        return main, wt
    return main, main


def launches(folder):
    return [l.rstrip("\n") for l in read(os.path.join(folder, "agent_state.txt")).splitlines(True)
            if l.startswith("LAUNCH ")]


def run(args):
    tmp = tempfile.mkdtemp(prefix="board_trust_dry_")
    try:
        return replay(args, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def replay(args, tmp):
    copy = os.path.join(tmp, "copy")
    files = []
    for src in sorted(glob.glob(os.path.join(args.projects, "**", "*.jsonl"), recursive=True)):
        dst = os.path.join(copy, os.path.relpath(src, os.path.dirname(args.projects.rstrip("/*"))))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        files.append(dst)
    items, ids = [], set()
    for f in files:
        uses, results = tool_uses(f)
        for d, c in uses:
            if c.get("id") not in ids and local_now(d.get("timestamp", ""))[:10] >= args.since:
                ids.add(c.get("id"))
                items.append((d, c, results.get(c.get("id")), f))
    items.sort(key=lambda x: x[0].get("timestamp", ""))
    stub = os.path.join(tmp, "stub")
    os.makedirs(stub)
    with open(os.path.join(stub, "orca"), "w") as fh:
        fh.write("#!/bin/sh\necho 'orca stub: down' >&2\nexit 1\n")
    os.chmod(os.path.join(stub, "orca"), 0o755)
    cfg = os.path.join(tmp, "cfg")
    os.makedirs(cfg)
    current, done = todo_names(args.main)
    n = collections.Counter()
    blocks, loud, kept = [], [], []
    for i, (d, c, res, tpath) in enumerate(items):
        cwd = d.get("cwd") or ""
        side = bool(d.get("isSidechain") or d.get("agentId"))
        own = cwd[len(args.workspaces):].split("/")[0] if cwd.startswith(args.workspaces) else ""
        role = "free" if side else "main" if (cwd == args.main or cwd.startswith(args.main + "/")) else \
            "tm" if own else "free"
        now = local_now(d.get("timestamp", ""))
        opened = sorted(set(current) | {k for k, v in done.items() if v >= now[:10]})
        base = os.path.join(tmp, "r%04d" % i)
        main, folder = make_repo(base, args.repo, opened, role, own or "task", args.conf)
        env = {k: v for k, v in os.environ.items() if k in ("HOME", "LANG", "LC_ALL", "TMPDIR", "USER")}
        env.update({"PATH": stub + ":" + os.environ.get("PATH", "/usr/bin:/bin"), "CLAUDE_PID": str(LIVE),
                    "CLAUDE_CONFIG_DIR": cfg, "AGENT_FAKE_NOW": now})
        if role == "tm":
            env["AGENT_ROLE"] = "task-manager"
        name, inp = c.get("name"), dict(c.get("input") or {}, prompt="brief")
        pre = {"session_id": d.get("sessionId", "s"), "transcript_path": tpath, "cwd": folder,
               "hook_event_name": "PreToolUse", "tool_name": name, "tool_input": inp, "tool_use_id": c.get("id")}
        if side:
            pre.update(agent_id=d.get("agentId") or "a_side", agent_type="general-purpose")

        def hook(payload):
            r = subprocess.run(["bash", GUARD], input=json.dumps(payload), cwd=folder, env=env,
                               capture_output=True, text=True, timeout=15)
            return r.returncode, r.stderr.strip()

        what = inp.get("description") if name != "Bash" else (inp.get("command") or "")[:160]
        n["launches"] += 1
        n["role " + role] += 1
        before = len(launches(folder))
        rc, err = hook(pre)
        if rc == 2:
            n["blocked"] += 1
            blocks.append((now, role, own, what, err))
            shutil.rmtree(base, ignore_errors=True)
            continue
        n["allowed"] += 1
        if err:
            loud.append((now, role, what, err))
        recorded = len(launches(folder)) > before
        n["recorded" if recorded else "not recorded"] += 1
        if not recorded:  # why: an orca call that is not a pane create, a checked worktree create, else an agent
            m = re.search(r"orca\s+(terminal|worktree)\s+(\w+)", inp.get("command") or "") if name == "Bash" else None
            why = ("orca %s %s" % m.groups() if m else "orca (other)") if name == "Bash" else "agent (unknown pid or off)"
            if why in ("orca terminal create", "orca worktree create"):
                why += " in text only (grep, heredoc, script), not a launch" if why.endswith("terminal create") \
                    else ", checked, never recorded"
            n["  not recorded: " + why] += 1
        if isinstance(res, dict) and name == "Bash":
            response = {"stdout": res.get("stdout", ""), "stderr": res.get("stderr", ""),
                        "interrupted": res.get("interrupted", False)}
        elif isinstance(res, dict):
            response = res
        else:
            response = {"stdout": str(res or ""), "stderr": "", "interrupted": False} if name == "Bash" \
                else {"status": "completed"}
        hook(dict(pre, hook_event_name="PostToolUse", tool_response=response))
        aid = res.get("agentId") if isinstance(res, dict) else None
        if aid and any(" | agent %s" % aid in l for l in launches(folder)):
            n["linked"] += 1
            hook({"session_id": pre["session_id"], "transcript_path": tpath, "cwd": folder,
                  "hook_event_name": "SubagentStop", "agent_id": aid, "agent_type": inp.get("subagent_type", "")})
        if recorded and name != "Bash":
            if len(launches(folder)) == before:
                n["agent record gone at the end"] += 1
            else:
                kept.append((now, role, what, launches(folder)[-1]))
        shutil.rmtree(base, ignore_errors=True)
    return n, blocks, loud, kept


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    main_dir = main_worktree(ROOT)
    ap.add_argument("--repo", default=os.path.basename(main_dir))
    ap.add_argument("--main", default=main_dir)
    ap.add_argument("--workspaces", default=None)
    ap.add_argument("--projects", default=None)
    ap.add_argument("--since", default="0000-00-00")
    ap.add_argument("--switch", choices=("on", "record", "off"), default="",
                    help="board_guard for the replay; default: the repo's own agent.conf")
    args = ap.parse_args()
    global SWITCH
    SWITCH = args.switch
    args.main = os.path.realpath(args.main)
    # the repo's own switch (auto-pipeline: board_guard=on); the template (default record) when it has none
    args.conf = os.path.join(args.main, "agent.conf")
    if not os.path.isfile(args.conf):
        args.conf = os.path.join(ROOT, "bin", "agent.conf.default")
    args.workspaces = (args.workspaces or os.path.expanduser("~/orca/workspaces/%s" % args.repo)).rstrip("/") + "/"
    args.projects = args.projects or os.path.join(os.path.expanduser("~/.claude/projects"), "*%s*" % args.repo)
    n, blocks, loud, kept = run(args)
    print("dry-run %s since %s, switch %s:" % (args.repo, args.since, args.switch or "from " + args.conf))
    for k, v in sorted(n.items(), key=lambda kv: (kv[0].startswith(" "), kv[0])):
        print("  %s %d" % (k, v))
    for b in blocks:
        print("BLOCK %s %s%s %r -> %s" % (b[0], b[1], " " + b[2] if b[2] else "", (b[3] or "")[:100], b[4]))
    for l in loud:
        print("LOUD %s %s %r -> %s" % (l[0], l[1], (l[2] or "")[:80], l[3]))
    for k in kept[:20]:
        print("KEPT %s %s %r -> %s" % (k[0], k[1], (k[2] or "")[:80], k[3][:160]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
