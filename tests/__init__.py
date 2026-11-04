import os

# personal-mode: a test run in-process (agent_city.agent_command, agent_conf)
# never reads the real ~/.claude/auto-pipeline.conf of the machine running it.
os.environ["AUTO_PIPELINE_USER_CONF"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "no-such-dir", "auto-pipeline.conf")
for _key in ("ANTHROPIC_MODEL", "CLAUDE_CODE_EFFORT_LEVEL", "AUTO_PIPELINE_VERSION_URL"):
    os.environ.pop(_key, None)
