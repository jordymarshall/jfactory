# jfactory setup record

One record per repository. Re-running setup updates it; do not add another. `scripts/setup_check.py` reads this file, so keep the headings, table columns and the `Task location:` line.

## Readiness

Last reviewed <date> against `<base>` at `<commit>`.

| Area | State | Evidence or reason |
| --- | --- | --- |
| Documentation | <state> | <evidence, or the gap and who acts next> |
| Product direction | <state> | <evidence, or the gap and who acts next> |
| Workspace tools | <state> | <evidence, or the gap and who acts next> |
| Verification | <state> | <evidence, or the gap and who acts next> |
| Environments | <state> | <evidence, or the gap and who acts next> |
| PR delivery | <state> | <evidence, or the gap and who acts next> |

States: `verified`, `configured but unverified`, `blocked`, `not run by request`, `not applicable`.

## Owner interview

Ask every question during setup, even when the code suggests an answer; code shows what exists, not what the customer needs. Put the agent's proposal in the question when it helps. Leave the answer as `unanswered` until the owner replies. Product direction can be `verified` only when every row has the owner's answer.

| Question | Owner answer | Date |
| --- | --- | --- |
| Who is this for, and who struggles today? | unanswered | |
| What do they do today instead, and what is painful about it? | unanswered | |
| What outcome would they notice, and how would we know it improved? | unanswered | |
| What is out of scope? | unanswered | |
| What is the next bounded objective? | unanswered | |

## Open owner decisions

1. <decision needed, options, recommendation>

## Next objective

Task location: <where objectives live, for example "GitHub issues labelled jfactory-objective">

<link to the next objective and its state: proposed, agreed, in progress or done>
