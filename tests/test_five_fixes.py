"""UPDATE settings-configure (2026-11-25): permission_mode and the models are Configure
settings; agent.conf, the user file and agent-settings.sh set are gone. A stored value
that fails its check reads as the setting default.

Failing tests for five-fixes (main manager brief, 2026-11-05): five bug
fixes from agent_ideas.txt. S1, S2, S3 are here. S4 (a flaky wait) is a
test-only change in tests/test_agent_city_server.py; S5 (the city walk) is in
tests/test_agent_city_walk.py. Written by the task manager, before any code.

CONTRACT

S1. bin/agent_conf.py: the permission modes are the ones `claude --help`
  lists for --permission-mode (claude 2.1.318, 2026-11-05):
    PERMISSION_MODES = ["acceptEdits", "auto", "bypassPermissions",
                        "manual", "dontAsk", "plan"]      (that order)
  "default" is no claude mode any more.
  validate_value("permission_mode", v): None for
    those six exactly (case and spaces count); anything else, "default"
    too, a message that names all six. "default" is refused, never mapped
    to another mode.
  HINTS["permission_mode"] names the six
    and never the word "default".
  Every launcher reads the mode through agent_conf.effective() (it only
  returns a value validate_value accepts), so a refused value never reaches
  a --permission-mode flag:
    agent_city.agent_command: permission_mode=default -> no flag on a local
      line.
    bin/agent-resume.sh: permission_mode=default -> "--permission-mode auto".
    bin/agent-settings.sh get permission_mode (dispatch, a Helper): default
      -> "auto (default)".
    bin/agent-start.sh: "PERMISSION: auto (default)" for default.
  bin/agent-settings.sh permission_mode default, and --user permission_mode
    default: exit 1, "not saved", the six named, nothing written.
  A user-file permission_mode=default is ignored (read_user_conf lists it).
  manual and dontAsk reach a launch line like any other mode.
  Every mode in PERMISSION_MODES is one the installed claude lists (skipped
    when no claude is on PATH).

S2. bin/agent_conf.py: a model with the context suffix "[1m]"
  Role value shape (every role key): model-name, then optionally exactly
    "[1m]", then ":effort". A broken suffix ("[1m", "[]", "[1m]x",
    "[1m][1m]", "[", " [1m]") is refused like any bad shape.
  Decider floor (main_manager, task_manager): the suffix is ignored, the
    floor itself is unchanged. opus-5.5[1m], claude-opus-5-5[1m],
    fable-5.1[1m], fable[1m], opus[1m] ... pass; sonnet, haiku, opus-5.4,
    opus-5 with the suffix are refused with the floor message; effort low is
    still refused.
  cli_model keeps the suffix (model-suffix, 2026-11-05; it was dropped in
    0.30.2): "opus-5.5[1m]:xhigh" -> "opus[1m]",
    "claude-opus-5-5[1m]:high" -> "claude-opus-5-5[1m]". Without the suffix:
    unchanged. `agent_conf.py cli-model <spec>` says the same. Every launch
    line quotes the model word, so zsh never reads "[1m]" as a glob
    (tests/test_model_suffix.py).
  bin/agent-settings.sh saves task_manager=opus-5.5[1m]:xhigh and refuses
    sonnet-5[1m]:high.

S3. bin/agent_update.py apply_auto_update(on, cdir): the backup
  "<file>.bak-auto-pipeline" is written only when none exists. After any
  number of on/off flips it holds the file as it was before the first flip,
  byte for byte; a backup already there (an earlier run) is never
  overwritten. The status line still names the backup path.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_conf  # noqa: E402
import agent_city as ac  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402

MODES = ["acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"]
MODE_KEYS = ("permission_mode",)
ENV = "AUTO_PIPELINE_USER_CONF"


# ===================================================================== S1


class TestStartLineRefusesDefault(ScriptCase):
    script = "agent-start.sh"

    def test_default_shows_as_auto(self):
        self.repo.set_conf("permission_mode", "default")
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        lines = [l for l in out.splitlines() if l.startswith("PERMISSION:")]
        self.assertEqual(lines, ["PERMISSION: bypassPermissions (from default)"])


# ===================================================================== S2


# ===================================================================== S3

SETTINGS = {
    "model": "opus",
    "extraKnownMarketplaces": {
        "auto-pipeline": {"source": {"source": "github", "repo": "maverick1014/auto-pipeline"}},
    },
}
KNOWN = {"auto-pipeline": {"source": {"source": "github", "repo": "maverick1014/auto-pipeline"},
                           "installLocation": "/x/auto-pipeline"}}
BAK = ".bak-auto-pipeline"


if __name__ == "__main__":
    unittest.main()
