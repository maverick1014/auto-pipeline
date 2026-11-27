#!/usr/bin/env python3
"""agent_model.py - model-floor (requirements/model-floor.md; rule: PRINCIPLES.md W17, rules/roles.md).

The header [<model> <effort>] of an order is the sender's model and effort NOW, read from the sources
of the YOU line (flag, env, settings.json), never copied from the start text.

  agent_model.py hook      UserPromptSubmit hook: JSON on stdin; on a change since the last prompt of
                           the session, prints MODEL CHANGED (and BELOW FLOOR when under the floor)
  used by agent_guard.py   header_verdict()      refuse an order whose header is not the current value
  used by agent_checks.py  record_ok(), holds()  the MODEL OK record (owner words verified by the caller)

Python 3.9 stdlib only. Never raises out of hook().
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HEADER = re.compile(r"\s*\[([A-Za-z][A-Za-z0-9.\-]*(?:\[1m\])?)\s+(low|medium|high|xhigh|max)\]")
READABLE = ("flag", "env", "settings.json")
FAMILY = re.compile(r"^([a-z]+)(?:-(\d+(?:\.\d+)?))?$")
RECORD = "agent_model_ok.json"


def _conf():
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import agent_conf
        return agent_conf
    finally:
        sys.dont_write_bytecode = old


def norm(model):
    """claude-opus-5-5[1m] -> opus-5.5; a short or bare name stays as it is."""
    name = re.sub(r"\[1m\]$", "", model.strip())
    name = name[7:] if name.startswith("claude-") else name
    m = re.match(r"^(opus|sonnet|haiku|fable)-(\d{1,2})-(\d{1,2})(?:-\d{8})?$", name)
    return "%s-%s.%s" % m.groups() if m else name


def same(a, b):
    """The same model; a bare family word (opus) is the newest and matches any version of it."""
    pa, pb = FAMILY.match(norm(a)), FAMILY.match(norm(b))
    if not pa or not pb:
        return norm(a) == norm(b)
    return pa.group(1) == pb.group(1) and (not pa.group(2) or not pb.group(2) or pa.group(2) == pb.group(2))


def below_floor(model, effort):
    """Under the decider floor (W17): not Opus 5.5 or above or Fable, or effort low."""
    return effort == "low" or not _conf()._meets_model_floor(norm(model))


def current(pid):
    """(model, effort) of the session now, or None when a source is not flag, env or settings.json."""
    try:
        line = _conf()._you_cli("main_manager", pid)
    except Exception:
        return None
    m = re.match(r"YOU: (\S+) (\S+) \(model: ([^,]*), effort: ([^)]*)\)", line)
    if m and m.group(3) in READABLE and m.group(4) in READABLE and m.group(1) != "unknown":
        return norm(m.group(1)), m.group(2)
    return None


def session_pid():
    v = os.environ.get("CLAUDE_PID", "").strip()
    if v:
        return int(v) if v.isdigit() and int(v) > 0 else None
    p = os.getppid()
    for _ in range(10):
        if p <= 1:
            break
        r = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(p)], capture_output=True, text=True, timeout=2)
        parts = r.stdout.strip().split(None, 1)
        if len(parts) < 2:
            break
        if os.path.basename(parts[1].strip()) == "claude":
            return p
        if not parts[0].isdigit():
            break
        p = int(parts[0])
    return None


def common_dir(cwd):
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ------------------------------------------------------------------ the MODEL OK record

def read_record(common):
    try:
        with open(os.path.join(common, RECORD), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def holds(common, model, effort):
    """True while the owner's MODEL OK stands for exactly this model and effort."""
    rec = read_record(common) if common else None
    return bool(rec and rec.get("effort") == effort and same(str(rec.get("model", "")), model))


def record_ok(common, model, effort, quote, means, question, typed):
    rec = {"model": model, "effort": effort, "quote": quote, "means": means, "typed": typed}
    if question:
        rec["question"] = question
    tmp = os.path.join(common, RECORD + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    os.replace(tmp, os.path.join(common, RECORD))


def end_record(common):
    try:
        os.remove(os.path.join(common, RECORD))
    except OSError:
        pass


# ------------------------------------------------------------------ the guard's check

def header_verdict(text, pid):
    """(block, note) for an order text: block is the refusal line or None, note a one-line note or None."""
    m = HEADER.match(text or "")
    if not m:
        return None, None
    cur = current(pid)
    if cur is None:
        return None, "board guard: your model could not be read; header not checked; allowed"
    shown = "%s %s" % cur
    if not same(m.group(1), cur[0]) or m.group(2) != cur[1]:
        return ("board guard: header [%s %s] is not your model [%s]: write [%s]" % (m.group(1), m.group(2), shown, shown),
                None)
    return None, None


def below_floor_verdict(common, pid, role):
    """The refusal line for a main manager under the floor without the owner's MODEL OK, else None."""
    cur = current(pid)
    if role != "main" or cur is None or not below_floor(*cur) or holds(common, *cur):
        return None
    return ("board guard: you run [%s %s], below the floor, and the owner has not said it is intended: ask him "
            "first (W17)" % cur)


# ------------------------------------------------------------------ the hook

def hook(raw):
    """Print MODEL CHANGED / BELOW FLOOR lines for one UserPromptSubmit payload."""
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("agent_id") or os.environ.get("AGENT_ROLE"):
        return []
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("session_id") or ""))
    common = common_dir(str(payload.get("cwd") or os.getcwd()))
    cur = current(session_pid())
    if not sid or not common or cur is None:
        return []
    path = os.path.join(common, "agent_model_%s" % sid)
    old = None
    try:
        with open(path, encoding="utf-8") as fh:
            parts = fh.read().split()
        old = (parts[0], parts[1]) if len(parts) == 2 else None
    except OSError:
        pass
    rec = read_record(common)
    if rec and not (rec.get("effort") == cur[1] and same(str(rec.get("model", "")), cur[0])):
        end_record(common)
    if old == cur:
        return []
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("%s %s\n" % cur)
    if old is None:
        return []
    out = ["MODEL CHANGED: %s %s -> %s %s" % (old + cur)]
    if below_floor(*cur):
        out.append("BELOW FLOOR: ask the owner first")
    return out


def main(argv):
    if argv[:1] == ["hook"]:
        try:
            lines = hook(sys.stdin.read())
        except Exception:
            lines = []
        for line in lines:
            print(line)
        return 0
    sys.stderr.write("usage: agent_model.py hook\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
