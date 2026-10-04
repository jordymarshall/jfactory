#!/usr/bin/env python3
"""Claude Code PreToolUse hook: in-session subagents only read.

Parallel or large writing work goes to separate Conductor workspaces through coord.py
(references/coordination.md). A subagent in the same session shares one checkout and
machine, and the owner cannot see or steer it. Read-only research helpers stay allowed.

Register it in .claude/settings.json (templates/claude-settings.json):

    {"hooks": {"PreToolUse": [{"matcher": "Agent|Task", "hooks": [{"type": "command",
      "command": "python3 \\"$CLAUDE_PROJECT_DIR/<bundle>/scripts/claude_subagent_guard.py\\""}]}]}}

The read-only types are Claude Code's built-in agents without edit tools. A repository adds
its own read-only agent types as "read_only_subagents" in .jfactory/coordination.json.
"""
import json
import os
import sys
from pathlib import Path

READ_ONLY = {'Explore', 'Plan', 'claude-code-guide', 'statusline-setup'}


def allowed_types(root):
    try:
        config = json.loads((Path(root) / '.jfactory' / 'coordination.json').read_text())
    except (OSError, ValueError):
        return set(READ_ONLY)
    extra = config.get('read_only_subagents', [])
    return READ_ONLY | {name for name in extra if isinstance(name, str)}


def decide(event, root):
    """Return the reason to deny this tool call, or None to allow it."""
    if event.get('tool_name') not in ('Agent', 'Task'):
        return None
    tool_input = event.get('tool_input') or {}
    kind = tool_input.get('subagent_type') or 'general-purpose'
    allowed = allowed_types(root)
    if kind in allowed and tool_input.get('isolation') is None:
        return None
    return (f'jfactory: in-session subagents may only do read-only research ({", ".join(sorted(allowed))}); '
            f'"{kind}"' + (f' with isolation "{tool_input["isolation"]}"' if tool_input.get('isolation') else '')
            + ' can change files. Do one unit of work yourself in this session. When the work splits into '
            'independent units or is too big for one session, propose the split to the owner and launch Conductor '
            'workspaces with coord.py (jfactory references/coordination.md). For research, use subagent_type '
            '"Explore".')


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # Not a hook event; never block on a malformed input.
    reason = decide(event, event.get('cwd') or os.environ.get('CLAUDE_PROJECT_DIR') or '.')
    if reason:
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                 'permissionDecisionReason': reason}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
