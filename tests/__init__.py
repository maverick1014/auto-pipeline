import atexit
import os
import shutil
import tempfile

# personal-mode / auto-update: a test never reads or writes the real
# ~/.claude/auto-pipeline.conf or the real Claude config dir (settings.json,
# plugins/known_marketplaces.json) of the machine running it, nor a file in
# this repo, even a test that starts a script outside tests/scripthelp.py.
# One throwaway folder per test run, removed at exit.
_TMP = tempfile.mkdtemp(prefix="auto_pipeline_tests_")
atexit.register(shutil.rmtree, _TMP, True)
os.environ["AUTO_PIPELINE_USER_CONF"] = os.path.join(_TMP, "user", "auto-pipeline.conf")
os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(_TMP, "no-claude-config")
for _key in ("ANTHROPIC_MODEL", "CLAUDE_CODE_EFFORT_LEVEL", "AUTO_PIPELINE_VERSION_URL"):
    os.environ.pop(_key, None)
