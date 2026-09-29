# Original pstack methods

Read the selected original and its relevant references. The compatibility mapping and current repository authorization apply. Supporting principles stay available under the original names.

| Request | Read and follow the original |
| --- | --- |
| How a subsystem works | [how](../vendor/pstack/skills/how/SKILL.md) |
| Why a decision was made | [why](../vendor/pstack/skills/why/SKILL.md) |
| Help the owner understand a change | [teach](../vendor/pstack/skills/teach/SKILL.md), including its how/why/unslop dependencies as needed |
| Fix a bug with a cheap local reproduction | [tdd](../vendor/pstack/skills/tdd/SKILL.md) |
| Verify completed work | [prove-it-works](../vendor/pstack/skills/principle-prove-it-works/SKILL.md) and the target repository’s generated verifier |
| Create missing project verification instructions | [create-verification-skill](../vendor/pstack/skills/create-verification-skill/SKILL.md) |
| Audit/update the verification map | [maintain-verification-skill](../vendor/pstack/skills/maintain-verification-skill/SKILL.md), with [guided mapping](mapping.md) and `verify_plan.py audit` for `.jfactory/verification.json` |
| Adversarial code review | [interrogate](../vendor/pstack/skills/interrogate/SKILL.md); report available reviewer/model limits |
| Evaluate a skill or prompt change | [eval playbook](../vendor/pstack/skills/poteto-mode/playbooks/eval.md), [arena](../vendor/pstack/skills/arena/SKILL.md) phases B/C and its referenced principles |
| Settle a design or empirical question before building | [prototype](../vendor/pstack/skills/poteto-mode/playbooks/prototype.md); the result is throwaway evidence for a decision |
| Choose a module shape before implementation | [architect](../vendor/pstack/skills/architect/SKILL.md), which uses how, why and arena |
| Split a large change into ordered PRs | [multi-PR plan](../vendor/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md) and [sequence verifiable units](../vendor/pstack/skills/principle-sequence-verifiable-units/SKILL.md), with [coordination translations](compatibility.md#coordination-translations) |
| Deliver several objectives through separate workspaces | jfactory's [coordination procedure](coordination.md), which adapts [orchestrate](../vendor/pstack/skills/poteto-mode/playbooks/orchestrate.md) |
| Drive one objective to a checkable done condition | [autonomous run](../vendor/pstack/skills/poteto-mode/playbooks/autonomous-run.md), within the objective contract |
| Resume or pause another session's work | [session pickup](../vendor/pstack/skills/poteto-mode/playbooks/session-pickup.md), [pause safely](../vendor/pstack/skills/poteto-mode/playbooks/pause-safely.md) |
| Keep an unattended decision trail | [show-me-your-work](../vendor/pstack/skills/show-me-your-work/SKILL.md); use one task-local trail with links from the existing task |


The supporting principles cover proving behavior, testing public behavior, fixing root causes, minimizing unnecessary complexity, reconsidering design when requirements change, isolating concurrent state, encoding recurring lessons in executable structure, sequencing verifiable units, exploring alternative designs, protecting the context window and avoiding unnecessary owner blocking. Use them when the selected workflow calls for them.
