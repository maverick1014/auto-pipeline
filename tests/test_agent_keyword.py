"""bin/agent-keyword.sh: keyword in the prompt -> one line naming the skill."""
import json, os, subprocess, unittest

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


if __name__ == "__main__":
    unittest.main()
