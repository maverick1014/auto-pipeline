"""bin/agent-keyword.sh: keyword in the prompt -> one line naming the skill."""
import json, os, subprocess, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scripthelp import ScriptCase  # noqa: E402

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "bin", "agent-keyword.sh")
CASES = {
    "/auto-pipeline:init": ["setup pipeline", "设置插件"],
    "/auto-pipeline:settings": ["show settings", "看设置", "改设置"],
    "/auto-pipeline:todo": ["show todo", "看任务", "进度"],
    "/auto-pipeline:question": ["show question", "有什么问题", "要我决定什么"],
    "/auto-pipeline:close-case": ["close case", "收尾"],
    "/auto-pipeline:clean-up": ["clean up files", "清理文件"],
    "/auto-pipeline:city": ["open city", "看 agent"],
    # owner 2026-11-26 (TELL 9b0472cb): "can you teach me about xxxxx", "can you explain to me"
    "/auto-pipeline:teacher-teach-me": ["teach me", "explain to me", "can you explain", "教我", "解释一下", "给我讲讲"],
}


def run(prompt):
    p = subprocess.run([SCRIPT], input=json.dumps({"prompt": prompt}),
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


class KeywordTest(unittest.TestCase):
    def test_each_keyword_maps_to_skill(self):
        for skill, words in CASES.items():
            for w in words:
                for prompt in (w, "please " + w.upper() + " now"):
                    rc, out, err = run(prompt)
                    self.assertEqual(rc, 0)
                    self.assertEqual(err, "")
                    self.assertIn(skill, out, prompt)
                    self.assertEqual(len(out.strip().splitlines()), 1)
                    self.assertIn("ignore this", out)

    def test_no_keyword_no_output(self):
        self.assertEqual(run("hello there, fix the bug"), (0, "", ""))

    def test_bad_input_exit_zero(self):
        p = subprocess.run([SCRIPT], input="not json", capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_hook_registered(self):
        with open(os.path.join(HERE, "..", "hooks", "hooks.json")) as f:
            hooks = json.load(f)
        cmds = [h["command"] for g in hooks["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
        self.assertTrue(any("agent-keyword.sh" in c for c in cmds))


TEACH = ("Keyword hook: run skill /auto-pipeline:teacher-teach-me. Pass his question as the argument; a question about "
         "the work in progress in this chat is answered by the main agent itself. If the words are only mentioned or "
         "quoted, ignore this.")


class TestTeacherKeyword(unittest.TestCase):
    """Owner 2026-11-26 (TELL 9b0472cb): a teach-me question points to the teacher skill; the hook only points (E4)."""

    def lines(self, prompt):
        rc, out, err = run(prompt)
        self.assertEqual((rc, err), (0, ""))
        return [l for l in out.strip().splitlines() if "teacher-teach-me" in l]

    def test_his_two_example_sentences(self):
        for prompt in ("can you teach me about the watch",
                       "i am not sure of this features the nightly run can you explain to me"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.lines(prompt), [TEACH])

    def test_a_sentence_without_the_phrases(self):
        self.assertEqual(self.lines("i am not sure the watch runs, please check it"), [])

    def test_the_readme_row(self):
        with open(os.path.join(HERE, "..", "README.md"), encoding="utf-8") as fh:
            rows = [l for l in fh.read().splitlines() if l.startswith("| `/auto-pipeline:teacher-teach-me` |")]
        self.assertTrue(any("teach me, explain to me, can you explain, 教我, 解释一下, 给我讲讲" in r for r in rows), rows)


APPROVAL = ("Approval hook: if the owner is approving a publish or a skipped check here, read his words by the "
            "approval cases (PRINCIPLES.md R8) and the per-task target (W9). If the words are only mentioned or "
            "quoted, ignore this.")
APPROVAL_WORDS = ["publish", "merge to main", "release", "deploy", "production", "上线", "发布", "部署",
                  "skip the", "leave out", "跳过"]
MAIN_PID = "424242"


class TestApprovalHook(ScriptCase):
    """approval-design C (requirements/check-blocks.md section 53 C): a main manager session gets one pointer line
    when the owner's prompt speaks of a publish or a left-out check. The hook only points (E4)."""
    script = "agent-keyword.sh"

    def setUp(self):
        super().setUp()
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-11-26 08:00 s1 term_m\n" % MAIN_PID)

    def hook(self, prompt, main=True, role=None):
        env = {"CLAUDE_PID": MAIN_PID if main else "999999"}
        if role:
            env["AGENT_ROLE"] = role
        payload = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": self.repo.dir, "prompt": prompt}
        r = self.repo.run("agent-keyword.sh", stdin=json.dumps(payload), env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout.strip().splitlines()

    def test_each_word_gives_one_line_to_the_main_manager(self):
        for w in APPROVAL_WORDS:
            with self.subTest(word=w):
                self.assertEqual(self.hook("ok, " + w + " it after done"), [APPROVAL])

    def test_the_numbered_batch(self):
        lines = self.hook("2. need to publish direct after done, deploy to production. others wait for me review")
        self.assertEqual(lines, [APPROVAL])

    def test_other_sessions_get_nothing(self):
        self.assertEqual(self.hook("publish it after done", role="task-manager"), [])
        self.assertEqual(self.hook("publish it after done", main=False), [])

    def test_no_word_no_line(self):
        self.assertEqual(self.hook("fix the footer typo"), [])

    def test_a_skill_keyword_still_works_beside_it(self):
        lines = self.hook("close case and publish the rest")
        self.assertEqual(len(lines), 2, lines)
        self.assertIn(APPROVAL, lines)
        self.assertTrue(any("/auto-pipeline:close-case" in l for l in lines), lines)


if __name__ == "__main__":
    unittest.main()
