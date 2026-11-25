#!/usr/bin/env bash
# agent-cleanup.sh — the cleanup sweep. One mechanical pass, never an agent.
#
#   agent-cleanup.sh            list: what --apply would do, then the kept table.
#                               Changes nothing (a git fetch is fine)
#   agent-cleanup.sh --apply    remove the SAFE items, then the kept table
#   agent-cleanup.sh --short    (with or without --apply) the hook form
#   agent-cleanup.sh --files            list rubbish docs, old state copies, finished mocks and
#                               outdated agent_* lines (dry run, changes nothing)
#   agent-cleanup.sh --files --yes <ids>|all|none   remove the rows the human picked
#   agent-cleanup.sh -h         this help
#
# Main manager only (role main or takeover, agent-roots.sh role_read). A spawned
# agent, a human-direct Helper and a closed session are refused before any orca
# or git call. The logic is bin/agent_cleanup.py (the sweep) and
# bin/agent_cleanfiles.py (--files); this file only checks the role, works out
# the runtime kind and hands over.

set -u
. "$(dirname "$0")/agent-roots.sh"

usage() {
  cat <<'EOF'
agent-cleanup.sh — remove what is finished: merged worktrees and branches, dead panes, leftover pipeline processes.

  agent-cleanup.sh             list what --apply would do, then the kept table (changes nothing)
  agent-cleanup.sh --apply     remove the SAFE items, then the kept table
  agent-cleanup.sh --short     the hook form (with or without --apply)
  agent-cleanup.sh --files     list rubbish docs, old state copies, finished mocks and outdated agent_* lines (dry run, changes nothing)
  agent-cleanup.sh --files --yes <ids>|all|none
                               remove the rows the human picked (ids as printed by --files, comma or space separated)
  agent-cleanup.sh -h          this help

--files never goes with --apply or --short. --yes needs a value and --files; all and none are not mixed with ids.
Nothing is removed without --yes.

Main manager only. A worktree is removed only when it is merged into the working branch or the production branch,
pushed, clean, on a branch, with no live agent and no working, final or
human-direct line in agent_worktree.txt. Never --force. A paired machine's
worktree is listed, never removed. Main and the release branch are never listed.
The list also names what --apply would do to LAUNCH records (a dead pid or a gone
pane: "would prune LAUNCH <key> (pid dead|pane gone)") and to panes that never got
a prompt and are idle over unused_pane_min ("would close pane <h> (<title>) in <path>:
never got a prompt, idle <n>m"). A worktree with a live LAUNCH record is "live agent".
EOF
}

APPLY=0
SHORT=0
FILES=0
HAVE_YES=0
YES=""
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0;;
    --apply) APPLY=1;;
    --short) SHORT=1;;
    --files) FILES=1;;
    --yes)
      if [ $# -lt 2 ] || [ -z "$2" ]; then
        echo "agent-cleanup.sh: --yes needs a value (ids, all or none)" >&2
        usage >&2; exit 2
      fi
      case "$2" in
        -*) echo "agent-cleanup.sh: --yes needs a value (ids, all or none)" >&2
            usage >&2; exit 2;;
      esac
      HAVE_YES=1
      YES="$2"
      shift;;
    *) usage >&2; exit 2;;
  esac
  shift
done

if [ "$FILES" = 1 ] && { [ "$APPLY" = 1 ] || [ "$SHORT" = 1 ]; }; then
  echo "agent-cleanup.sh: --files does not go with --apply or --short" >&2
  usage >&2; exit 2
fi
if [ "$HAVE_YES" = 1 ] && [ "$FILES" = 0 ]; then
  echo "agent-cleanup.sh: --yes needs --files" >&2
  usage >&2; exit 2
fi
if [ "$HAVE_YES" = 1 ]; then
  case "$YES" in
    *[!A-Za-z0-9,\ ]*)
      echo "agent-cleanup.sh: --yes takes ids, all or none, nothing else" >&2
      usage >&2; exit 2;;
  esac
  n_all=0; n_none=0; n_other=0
  for tok in $(printf '%s' "$YES" | tr 'A-Z,' 'a-z '); do
    case "$tok" in
      all) n_all=1;;
      none) n_none=1;;
      *) n_other=1;;
    esac
  done
  if [ $((n_all + n_none + n_other)) = 0 ]; then
    echo "agent-cleanup.sh: --yes needs a value (ids, all or none)" >&2
    usage >&2; exit 2
  fi
  if [ $((n_all + n_none)) -gt 0 ] && [ $((n_all + n_none + n_other)) -gt 1 ]; then
    echo "agent-cleanup.sh: --yes: all and none stand alone, never with ids" >&2
    usage >&2; exit 2
  fi
fi

roots_read
role_read
case "$role" in
  spawned|second|closed)
    echo "REFUSED: cleanup is main manager only (role $role)." >&2
    exit 1;;
esac

ROOT="$PROJECT_ROOT"
PLUGIN="$PLUGIN_ROOT"
. "$(dirname "$0")/agent-runtime.sh"
KIND=$(runtime_kind)

if [ "$FILES" = 1 ]; then
  fargs=(--root "$ROOT" --plugin "$PLUGIN" --gitdir "$PROJECT_GITDIR" --kind "$KIND")
  [ "$HAVE_YES" = 1 ] && fargs+=(--yes "$YES")
  exec python3 "$PLUGIN/bin/agent_cleanfiles.py" "${fargs[@]}"
fi

args=(--root "$ROOT" --plugin "$PLUGIN" --kind "$KIND")
[ "$APPLY" = 1 ] && args+=(--apply)
[ "$SHORT" = 1 ] && args+=(--short)
exec python3 "$PLUGIN/bin/agent_cleanup.py" "${args[@]}"
