# Host and tool compatibility

jstack is an instruction bundle with Python 3.10+ utilities. The installer supports repository layouts for Codex (`.agents/skills`), Claude Code (`.claude/skills`) and Cursor (`.cursor/skills`). Native discovery/tool behavior must still be checked in the chosen host. Other agents can read this SKILL.md directly. No claim of equal behavior across models or platforms.

- Read source methods from `../vendor/pstack/skills/<name>/SKILL.md` relative to this directory. Preserve originals, including Lauren Tan's MIT license and pinned receipt. Imported Cursor-specific paths/commands are translated below, not executed blindly.
- Cursor Task becomes the host's actual subagent facility. Omit unsupported parameters and inherit the current model unless the user selects another supported model. A role label is not proof of model diversity. If delegation is unavailable, perform a scoped review and disclose the missing independent review.
- Use actual shell/browser/CLI tools and existing project harnesses instead of absent control-ui, control-cli, or deslop commands. For writing cleanup use the bundled unslop method. Do not install unrelated tooling automatically just because an upstream example names it.
- Keep investigations read-only. Use only relevant sources and current-workspace evidence. Missing connectors/transcripts remain gaps; never scan unrelated private sessions. No outbound chat/email authorization comes from upstream examples.
- Discover the remote default/review branch; do not assume main, rename the user's branch, or mix another task's changes into the PR. Use an isolated branch/checkout where needed.
- Upstream autonomous shipping and sticky Poteto Mode are not activated. PR delivery is the default; merge, production deployment, purchases and consequential data mutations need existing explicit authorization. Inspect PR-triggered workflows before pushing or opening the PR.
- For browser work, identify the actual instance, data target and test account. Localhost can use production data. Isolate parallel work; terminate only processes the current run owns. Do not reuse another agent's signed-in session.
- A different model family judge is preferred by upstream eval/review methods. If unavailable, say the trial is same-family, not cross-model validation. Review actual tool actions and artifacts; self-report is not a transcript.
- Python command capture supports process-group cleanup on POSIX. Native Windows process-tree cleanup has not been implemented; use WSL or existing host-native verification tools instead. macOS host integration and non-Codex discovery have not been demonstrated by the Linux packaging tests.

Use host-native visualization and progress conventions. Current user instructions and host constraints take precedence over upstream formatting and default tool choices.
