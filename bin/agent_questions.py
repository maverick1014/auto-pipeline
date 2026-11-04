#!/usr/bin/env python3
"""agent_questions.py - the work behind `agent-file.sh questions`, `park add` and `park rm --id`
("show question"). Python 3.9, standard library only, no imports of sibling modules.

    agent_questions.py <root> <state-dir> <cwd> <now> <lang> <command> [args...]

Commands: list [--self] [--json] | list [--self] --page <file> | url <url> | answer <id> <text>
          | park-add <question> [<task>] [flags] | park-rm-id <id>

Reads agent_todo.txt, agent_worktree.txt and the agent_state.txt files; writes only what a command
says (atomic: tmp + replace). A refusal is one line on stderr, exit 1, nothing written.
"""

import datetime
import hashlib
import json
import os
import re
import sys

DATE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
HELPER_ROLE = "task manager, human-direct"
OPEN_KINDS = ("mock", "question", "review")
LETTERS = "ABCDEFGH"
URL_RE = re.compile(r"^https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9_-]+$")
ID_BAD = re.compile(r"[^A-Za-z0-9_.~:@+-]")

WORDS = {
    "zh": {
        "what": "内容", "where": "位置", "from": "来自", "why": "为什么现在", "evidence": "依据",
        "rec": "建议", "recmark": "建议",
        "t_mock": "看一下 %s 的 mock", "t_question": "%s 有一个问题等你回答", "t_review": "验收 %s",
        "o_mock": ["可以，继续", "要改（写在备注里）"], "o_review": ["验收通过", "有问题（写在备注里）"],
        "mgr": "%s 任务经理",
    },
    "en": {
        "what": "What", "where": "Where", "from": "From", "why": "Why now", "evidence": "Evidence",
        "rec": "Recommendation", "recmark": "recommended",
        "t_mock": "Check the %s mock", "t_question": "%s has a question for you", "t_review": "Review %s",
        "o_mock": ["Yes, go on", "Change it (say how in the note)"],
        "o_review": ["Passed", "Something is wrong (say what in the note)"],
        "mgr": "the %s task manager",
    },
}


class Refuse(Exception):
    pass


# ---------------------------------------------------------------- small helpers


def read_text(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", "surrogateescape")
    except OSError:
        return None


def lines_of(path):
    text = read_text(path)
    if text is None:
        return []
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return [p[:-1] if p.endswith("\r") else p for p in parts]


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(text.encode("utf-8", "surrogateescape"))
    os.replace(tmp, path)


def sha10(text):
    return hashlib.sha1(text.encode("utf-8", "surrogateescape")).hexdigest()[:10]


def base(path):
    return os.path.basename(path.rstrip("/")) or path


def digits(text):
    return re.sub(r"\D", "", text)


def bad_text(text):
    return " | " in text or "\n" in text or "\r" in text


# ---------------------------------------------------------------- the collector


class Collector:
    def __init__(self, root, state_dir, cwd, now, lang):
        self.root = os.path.normpath(root)
        self.state_dir = os.path.normpath(state_dir)
        self.cwd = cwd
        self.now = now
        self.lang = "zh" if lang == "zh" else "en"
        self.w = WORDS[self.lang]

    # -- reading the files

    def todo_lines(self):
        out = []
        for line in lines_of(os.path.join(self.root, "agent_todo.txt")):
            if not line.strip():
                continue
            t = self.parse_todo(line)
            if t["name"]:
                out.append(t)
        return out

    @staticmethod
    def parse_todo(line):
        f = line.split(" | ")
        t = {"name": f[0].strip(), "what": f[2] if len(f) > 2 else "", "wkind": None, "wsince": "",
             "wnote": "", "machine": None, "path": ""}
        for x in f[3:]:
            m = re.match(r"waiting (\S+) since (%s)(?:: (.*))?$" % DATE, x)
            if m and t["wkind"] is None:
                t["wkind"], t["wsince"], t["wnote"] = m.group(1), m.group(2), m.group(3) or ""
                continue
            m = re.match(r"on (\S+)(?: (.*))?$", x)
            if m and t["machine"] is None:
                t["machine"], t["path"] = m.group(1), (m.group(2) or "").strip()
        return t

    def wt_lines(self):
        return [l.split(" | ") for l in lines_of(os.path.join(self.root, "agent_worktree.txt")) if l.strip()]

    def own_todo_from_state(self):
        found = None
        for line in lines_of(os.path.join(self.state_dir, "agent_state.txt")):
            m = re.match(r"\s*TODO LINE: (.*)$", line)
            if m:
                found = m.group(1)
        return found

    # -- the question records

    def todo_question(self, t):
        kind, w = t["wkind"], self.w
        name = t["name"]
        title = t["wnote"].strip() or w["t_" + kind] % name
        facts = [[w["what"], t["what"]]]
        if t["machine"]:
            facts.append([w["where"], t["machine"] + (" " + t["path"] if t["path"] else "")])
        opts = []
        if kind in ("mock", "review"):
            opts = [{"letter": LETTERS[i], "text": x, "rec": False} for i, x in enumerate(w["o_" + kind])]
        qid = "t-%s-%s-%s" % (ID_BAD.sub("-", name), kind, digits(t["wsince"]))
        return {"id": qid, "source": "todo", "kind": kind, "task": name, "title": title, "sub": "",
                "facts": facts, "options": opts, "since": t["wsince"],
                "file": os.path.join(self.root, "agent_todo.txt"), "_name": name}

    def worktree_questions(self, folder, module):
        path = os.path.join(folder, "agent_state.txt")
        lines = lines_of(path)
        out = []
        for i, line in enumerate(lines):
            if not line.startswith("QUESTION:"):
                continue
            answered = False
            for later in lines[i + 1:]:
                if later.startswith("QUESTION:") or later.startswith("=== "):
                    break
                if later.lstrip(" ").startswith("ANSWER:"):
                    answered = True
                    break
            if answered:
                continue
            text = line[len("QUESTION:"):].strip()
            if not text:
                continue
            out.append({"id": "w-" + sha10("%s\n%s" % (module, text)), "source": "worktree", "kind": "",
                        "task": module, "title": text, "sub": "",
                        "facts": [[self.w["from"], self.w["mgr"] % module]], "options": [], "since": "",
                        "file": path, "_line": i})
        return out

    def parked_questions(self, folder):
        path = os.path.join(folder, "agent_state.txt")
        default_task = base(folder)
        out = []
        for i, line in enumerate(lines_of(path)):
            if not line.startswith("PARKED: "):
                continue
            parts = line[len("PARKED: "):].split(" | ")
            question = parts[0]
            rest = parts[1:]
            task = default_task
            if rest and not rest[0].startswith("since "):
                task = rest[0].strip() or default_task
                rest = rest[1:]
            since, sub, facts, options, rec = "", "", [], [], ""
            for x in rest:
                m = re.match(r"since (%s)" % DATE, x)
                if m and not since:
                    since = m.group(1)
                    continue
                if x.startswith("sub "):
                    sub = x[4:]
                    continue
                if x.startswith("fact "):
                    k, sep, v = x[5:].partition(": ")
                    if sep:
                        facts.append([k, v])
                    continue
                m = re.match(r"option ([A-H]): (.*)$", x)
                if m:
                    options.append({"letter": m.group(1), "text": m.group(2), "rec": False})
                    continue
                m = re.match(r"rec ([A-H])$", x)
                if m:
                    rec = m.group(1)
            for o in options:
                o["rec"] = o["letter"] == rec
            out.append({"id": "p-" + sha10("%s\n%s\n%s" % (task, question, since)), "source": "parked",
                        "kind": "", "task": task, "title": question, "sub": sub, "facts": facts,
                        "options": options, "since": since, "file": path, "_line": i})
        return out

    # -- the two views

    def collect(self, self_mode):
        root_real = os.path.realpath(self.root)
        wts = self.wt_lines()
        todos = self.todo_lines()
        by_name = {t["name"]: t for t in todos}
        not_read = []
        waits, folders = [], []   # folders: (path, module)

        if self_mode:
            name = base(self.state_dir)
            own = by_name.get(name)
            if own is None and os.path.realpath(self.state_dir) != root_real:
                line = self.own_todo_from_state()
                if line:
                    t = self.parse_todo(line)
                    own = t if t["name"] else None
            if own is not None and own["wkind"] in OPEN_KINDS:
                waits.append(own)
            if os.path.realpath(self.state_dir) != root_real:
                folders.append((self.state_dir, self.module_of(self.state_dir, wts)))
        else:
            waits = [t for t in todos if t["wkind"] in OPEN_KINDS]
            seen = set()
            order = [(self.root, base(self.root))]
            for f in wts:
                if f and f[0]:
                    order.append((f[0], self.module_of(f[0], wts)))
            for folder, module in order:
                norm = os.path.normpath(folder)
                if not os.path.isdir(norm):
                    if norm not in seen:
                        seen.add(norm)
                        mach = by_name.get(module, {}).get("machine") if module in by_name else None
                        not_read.append({"path": folder, "machine": mach or "another machine"})
                    continue
                real = os.path.realpath(norm)
                if real in seen:
                    continue
                seen.add(real)
                folders.append((norm, module))

        recs = [self.todo_question(t) for t in waits]
        for folder, module in folders:
            recs += self.worktree_questions(folder, module)
        for folder, _ in folders:
            recs += self.parked_questions(folder)

        # group by task, in order of first appearance
        order, groups = [], {}
        for r in recs:
            if r["task"] not in groups:
                groups[r["task"]] = []
                order.append(r["task"])
            groups[r["task"]].append(r)
        final, used = [], {}
        for task in order:
            for r in groups[task]:
                base_id = r["id"]
                if base_id in used:
                    used[base_id] += 1
                    r["id"] = "%s-%d" % (base_id, used[base_id])
                else:
                    used[base_id] = 1
                final.append(r)
        for n, r in enumerate(final, 1):
            r["n"] = n
        intros = {}
        for task in order:
            if task in by_name:
                intros[task] = by_name[task]["what"]
        return {"count": len(final), "questions": final, "not_read": not_read, "intros": intros}

    def module_of(self, folder, wts):
        real = os.path.realpath(folder)
        if real == os.path.realpath(self.root):
            return base(self.root)
        for f in wts:
            if len(f) >= 2 and f[0] and os.path.realpath(f[0]) == real:
                return base(f[0]) if f[1] == HELPER_ROLE else f[1].strip() or base(f[0])
        return base(folder)


# ---------------------------------------------------------------- output


PUBLIC = ("n", "id", "source", "kind", "task", "title", "sub", "facts", "options", "since", "file")


def public(q, with_file=True):
    return {k: q[k] for k in PUBLIC if with_file or k != "file"}


def render_text(data, lang):
    mark = WORDS[lang]["recmark"]
    out = ["QUESTIONS: %d" % data["count"]]
    blocks = []
    for q in data["questions"]:
        kind = {"parked": "parked", "todo": "todo " + q["kind"], "worktree": "task manager question"}[q["source"]]
        head = "%d. [%s] %s · %s" % (q["n"], q["id"], q["task"], kind)
        if q["since"]:
            head += " · since " + q["since"]
        b = [head, "   " + q["title"]]
        if q["sub"]:
            b.append("   — " + q["sub"])
        for k, v in q["facts"]:
            b.append("   %s: %s" % (k, v))
        for o in q["options"]:
            b.append("   %s. %s%s" % (o["letter"], o["text"], " (%s)" % mark if o["rec"] else ""))
        blocks.append(b)
    body = []
    for i, b in enumerate(blocks):
        if i:
            body.append("")
        body += b
    if body:
        out += [""] + body
    if data["not_read"]:
        out += [""] + ["not read: %s on %s" % (n["path"], n["machine"]) for n in data["not_read"]]
    return "\n".join(out) + "\n"


def safe_json(obj):
    s = json.dumps(obj, ensure_ascii=False)
    for ch, esc in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"),
                    (" ", "\\u2029")):
        s = s.replace(ch, esc)
    return s


# ---------------------------------------------------------------- state-file edits


def page_line_edit(state_path, make):
    """make(old_fields_or_None) -> new line. Replaces the first QUESTIONS PAGE line, drops others, else appends."""
    text = read_text(state_path) or ""
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    out, done = [], False
    for line in parts:
        if line.startswith("QUESTIONS PAGE: "):
            if not done:
                out.append(make(line[len("QUESTIONS PAGE: "):].split(" | ")))
                done = True
            continue
        out.append(line)
    if not done:
        out.append(make(None))
    write_atomic(state_path, "\n".join(out) + "\n")


def existing_url(state_path):
    for line in lines_of(state_path):
        if line.startswith("QUESTIONS PAGE: "):
            return line[len("QUESTIONS PAGE: "):].split(" | ")[0].strip() or "-"
    return "-"


def drop_line(path, index):
    text = read_text(path) or ""
    parts = text.split("\n")
    del parts[index]
    write_atomic(path, "\n".join(parts))


# ---------------------------------------------------------------- commands


def cmd_list(c, args):
    self_mode = json_out = False
    page = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--self":
            self_mode = True
        elif a == "--json":
            json_out = True
        elif a == "--page":
            if i + 1 >= len(args) or not args[i + 1]:
                raise Refuse("questions: --page needs a file")
            page = args[i + 1]
            i += 1
        else:
            raise Refuse("questions: unknown argument: %s" % a)
        i += 1
    if page is not None and json_out:
        raise Refuse("questions: --json and --page do not go together")
    data = c.collect(self_mode)
    if page is None:
        if json_out:
            sys.stdout.write(json.dumps({"count": data["count"], "questions": [public(q) for q in data["questions"]],
                                         "not_read": data["not_read"], "intros": data["intros"]},
                                        ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(render_text(data, c.lang))
        return
    write_page(c, data, page)


def write_page(c, data, page):
    page = os.path.abspath(os.path.join(c.cwd, page))
    mapf = (page[:-5] if page.endswith(".html") else page) + ".json"
    if not os.path.isdir(os.path.dirname(page)):
        raise Refuse("questions --page: no such folder: %s" % os.path.dirname(page))
    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-questions-page.html")
    tpl = read_text(tpl_path)
    if tpl is None or tpl.count("__SQ_DATA__") != 1:
        raise Refuse("questions --page: the page template is missing or has no data slot")
    qs = [public(q, with_file=False) for q in data["questions"]]
    payload = {"lang": c.lang, "repo": base(c.root), "generated": c.now, "intros": data["intros"], "questions": qs}
    html = tpl.replace("__SQ_DATA__", safe_json(payload))
    mapping = {"page": page, "generated": c.now,
               "questions": [{"n": q["n"], "id": q["id"], "task": q["task"], "title": q["title"],
                              "options": [o["letter"] for o in q["options"]]} for q in data["questions"]]}
    state = os.path.join(c.state_dir, "agent_state.txt")
    url = existing_url(state)
    write_atomic(page, html)
    write_atomic(mapf, json.dumps(mapping, ensure_ascii=False, indent=1) + "\n")
    page_line_edit(state, lambda old: "QUESTIONS PAGE: %s | %s | %s | since %s" % (url, page, mapf, c.now))
    sys.stdout.write("page: %s\nmap: %s\nquestions: %d\nurl: %s\n" % (page, mapf, data["count"], url))


def cmd_url(c, args):
    if len(args) != 1 or not URL_RE.match(args[0]):
        raise Refuse("questions --url: needs https://claude.ai/artifact/<id> or https://claude.ai/code/artifact/<id>")
    url = args[0]
    state = os.path.join(c.state_dir, "agent_state.txt")

    def make(old):
        if old is None or len(old) < 4:
            return "QUESTIONS PAGE: %s | - | - | since %s" % (url, c.now)
        return "QUESTIONS PAGE: %s | %s" % (url, " | ".join(old[1:]))
    page_line_edit(state, make)
    sys.stdout.write("url: %s\n" % url)


def cmd_answer(c, args):
    if len(args) != 2:
        raise Refuse("questions answer: needs <id> and \"<answer>\"")
    qid, answer = args
    if not answer.strip():
        raise Refuse("questions answer: the answer is empty")
    if "\n" in answer or "\r" in answer:
        raise Refuse("questions answer: the answer must not hold a line break")
    q = None
    for x in c.collect(False)["questions"]:
        if x["id"] == qid:
            q = x
            break
    if q is None:
        raise Refuse("questions answer: no open question with id: %s" % qid)
    short = q["title"][:60]
    if q["source"] == "todo":
        sys.stdout.write("@TODO-WAIT-OFF\t%s\nanswered %s: %s wait closed\n" % (q["_name"], qid, q["task"]))
    elif q["source"] == "parked":
        drop_line(q["file"], q["_line"])
        sys.stdout.write("answered %s: parked question removed: %s\n" % (qid, short))
    else:
        text = read_text(q["file"]) or ""
        parts = text.split("\n")
        parts.insert(q["_line"] + 1, "ANSWER: " + answer.strip())
        write_atomic(q["file"], "\n".join(parts))
        sys.stdout.write("answered %s: ANSWER line written under: %s\n" % (qid, short))


def clean_value(what, value):
    if value is None or not value.strip():
        raise Refuse("park add: %s is empty" % what)
    if bad_text(value):
        raise Refuse("park add: %s must not hold \" | \" or a line break" % what)
    v = value.strip()
    if v.startswith("|") or v.endswith("|"):
        raise Refuse("park add: %s must not start or end with \"|\"" % what)
    return v


def cmd_park_add(c, args):
    pos, items = [], []
    sub = options = None
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            if a not in ("--sub", "--why", "--evidence", "--fact", "--options", "--rec"):
                raise Refuse("park add: unknown option: %s" % a)
            if i + 1 >= len(args):
                raise Refuse("park add: %s needs a value" % a)
            val = args[i + 1]
            i += 2
            if a == "--sub":
                if sub is not None:
                    raise Refuse("park add: --sub twice")
                sub = clean_value("--sub", val)
            elif a == "--why":
                items.append(("fact", c.w["why"], clean_value("--why", val)))
            elif a == "--evidence":
                items.append(("fact", c.w["evidence"], clean_value("--evidence", val)))
            elif a == "--fact":
                v = clean_value("--fact", val)
                k, sep, rest = v.partition(": ")
                if not sep or not k.strip() or not rest.strip():
                    raise Refuse("park add: --fact is \"<key>: <value>\" with both parts")
                items.append(("fact", k.strip(), rest.strip()))
            elif a == "--options":
                if options is not None:
                    raise Refuse("park add: --options twice")
                clean_value("--options", val)
                options = [x.strip() for x in val.split("|")]
                if any(not x for x in options):
                    raise Refuse("park add: an option is empty")
                if len(options) > len(LETTERS):
                    raise Refuse("park add: at most %d options" % len(LETTERS))
            else:
                if any(it[0] == "rec" for it in items):
                    raise Refuse("park add: --rec twice")
                items.append(("rec", clean_value("--rec", val)))
        else:
            pos.append(a)
            i += 1
    if not pos:
        raise Refuse("park add: needs the question")
    if len(pos) > 2:
        raise Refuse("park add: too many arguments; quote the question")
    question = clean_value("the question", pos[0])
    task = clean_value("the task", pos[1]) if len(pos) > 1 and pos[1] != "" else base(c.state_dir)
    if not task:
        task = base(c.state_dir)
    facts, rec = [], ""
    for it in items:
        if it[0] == "fact":
            facts.append((it[1], it[2]))
        else:
            want = it[1]
            if options is None:
                facts.append((c.w["rec"], want))
                continue
            letter = ""
            if len(want) == 1 and want.upper() in LETTERS[:len(options)]:
                letter = want.upper()
            else:
                for j, o in enumerate(options):
                    if o.lower() == want.lower():
                        letter = LETTERS[j]
                        break
            if not letter:
                raise Refuse("park add: --rec is a letter or the text of an option")
            rec = letter
    fields = ["%s | %s | since %s" % (question, task, c.now)]
    if sub:
        fields.append("sub " + sub)
    for k, v in facts:
        fields.append("fact %s: %s" % (k, v))
    for j, o in enumerate(options or []):
        fields.append("option %s: %s" % (LETTERS[j], o))
    if rec:
        fields.append("rec " + rec)
    line = "PARKED: " + " | ".join(fields)
    state = os.path.join(c.state_dir, "agent_state.txt")
    text = read_text(state) or ""
    if text and not text.endswith("\n"):
        text += "\n"
    write_atomic(state, text + line + "\n")
    sys.stdout.write("parked: %s\nid: p-%s\n" % (question, sha10("%s\n%s\n%s" % (task, question, c.now))))


def cmd_park_rm_id(c, args):
    if len(args) != 1 or not args[0]:
        raise Refuse("park rm --id: needs one id")
    qid = args[0]
    own = os.path.realpath(os.path.join(c.state_dir, "agent_state.txt"))
    for self_mode in (False, True):
        for q in c.collect(self_mode)["questions"]:
            if q["id"] == qid and q["source"] == "parked" and os.path.realpath(q["file"]) == own:
                lines = lines_of(q["file"])
                n = sum(1 for l in lines[:q["_line"] + 1] if l.startswith("PARKED: "))
                drop_line(q["file"], q["_line"])
                sys.stdout.write("parked %d removed: %s\n" % (n, lines[q["_line"]][len("PARKED: "):][:60]))
                return
    raise Refuse("park rm --id: no parked question here with id: %s" % qid)


def main(argv):
    if len(argv) < 7:
        sys.stderr.write("agent_questions.py: needs root state-dir cwd now lang command\n")
        return 2
    root, state_dir, cwd, now, lang, cmd = argv[1:7]
    args = argv[7:]
    c = Collector(root, state_dir, cwd, now, lang)
    try:
        {"list": cmd_list, "url": cmd_url, "answer": cmd_answer, "park-add": cmd_park_add,
         "park-rm-id": cmd_park_rm_id}[cmd](c, args)
    except Refuse as e:
        sys.stderr.write(str(e).replace("\n", " ") + "\n")
        return 1
    except OSError as e:
        sys.stderr.write("%s: %s\n" % (cmd, str(e).replace("\n", " ")))
        return 1
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main(sys.argv))
