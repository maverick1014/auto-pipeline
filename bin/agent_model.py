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


def below_floor(model):
    """Under the decider floor (W17): not Opus 5.5 or above, or Fable (the model only: no effort source is
    session-true after an in-session /effort)."""
    return not _conf()._meets_model_floor(norm(model))


TAIL = 512 * 1024


def current(transcript):
    """The model THIS session runs now: the "model" of the latest assistant message of its transcript (the
    tail only). None when there is no transcript or no assistant message yet (fail open)."""
    try:
        with open(transcript, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError, ValueError):
        return None
    for line in reversed(lines):
        if '"assistant"' not in line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        msg = obj.get("message") if isinstance(obj, dict) else None
        name = msg.get("model") if isinstance(msg, dict) else None
        if obj.get("type") == "assistant" and isinstance(name, str) and name and not name.startswith("<"):
            return norm(name)
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


def holds(common, model):
    """True while the owner's MODEL OK stands for this model."""
    rec = read_record(common) if common else None
    return bool(rec and same(str(rec.get("model", "")), model))


def record_ok(common, model, quote, means, question, typed):
    rec = {"model": model, "quote": quote, "means": means, "typed": typed}
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

def header_verdict(text, transcript):
    """(block, note) for an order text: block is the refusal line or None, note a one-line note or None.
    Only the model is compared; an unreadable model is a note, never a refusal."""
    m = HEADER.match(text or "")
    if not m:
        return None, None
    cur = current(transcript)
    if cur is None:
        return None, "board guard: your model could not be read; header not checked; allowed"
    if not same(m.group(1), cur):
        return ("board guard: header [%s %s] is not your model [%s]: write [%s <your effort>]"
                % (m.group(1), m.group(2), cur, cur), None)
    return None, None


def below_floor_verdict(common, transcript, role):
    """The refusal line for a main manager under the floor without the owner's MODEL OK, else None."""
    cur = current(transcript)
    if role != "main" or cur is None or not below_floor(cur) or holds(common, cur):
        return None
    return ("board guard: you run [%s], below the floor, and the owner has not said it is intended: ask him "
            "first (W17)" % cur)


# ------------------------------------------------------------------ the hook

def seen_path(common, sid):
    return os.path.join(common, "agent_model_%s" % sid)


def read_seen(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("model")
    except (OSError, ValueError, AttributeError):
        return None


def hook(raw):
    """Print MODEL CHANGED / BELOW FLOOR lines for one UserPromptSubmit payload."""
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("agent_id") or os.environ.get("AGENT_ROLE"):
        return []
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("session_id") or ""))
    common = common_dir(str(payload.get("cwd") or os.getcwd()))
    cur = current(payload.get("transcript_path"))
    if not sid or not common or cur is None:
        return []
    path = seen_path(common, sid)
    old = read_seen(path)
    rec = read_record(common)
    if rec and old is not None and old != cur and not same(str(rec.get("model", "")), cur):
        end_record(common)
    with open(path, "w", encoding="utf-8") as fh:   # always: `model ok` reads the newest one
        json.dump({"model": cur}, fh)
    if old is None or old == cur:
        return []
    out = ["MODEL CHANGED: %s -> %s" % (old, cur)]
    if below_floor(cur):
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
