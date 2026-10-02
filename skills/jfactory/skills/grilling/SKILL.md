---
name: grilling
description: Establish shared goals and verifier criteria during jfactory setup, objective definition, or changes to product, engineering and UI intent. Reuse settled decisions and interview only about unresolved intent.
---

Read Matt Pocock's unchanged [grilling skill](../../vendor/mattpocock/skills/grilling/SKILL.md) and apply its design tree and frontier rounds within the current jfactory objective.

Start from the owner's request and canonical records. During first setup, cover the required [owner interview](../../references/setup.md#2-reconcile-the-foundation). On updates and resumed objectives, carry confirmed answers forward. For each objective, establish the customer outcome, scope, non-goals, affected job goals, observable acceptance criteria and their evidence. If these are already settled, record that and proceed; another confirmation is unnecessary. Ask each consequential unresolved decision with a recommendation; dependent implementation waits for the answer. Existing explicit authorization counts as confirmation within its scope.

Find technical facts from the repository and tools. Upstream's subagent instruction maps to the host's authorized delegation; inspect directly when delegation is unavailable or unnecessary. Use the host's supported question UI and formatting. Continue independent work while answers or investigations are pending.

Write answers and unresolved choices into the existing objective and setup record. When a decision changes standing intent, update the affected project-owned outcome/job documents, engineering sources, UI/UX sources and standards map in the same PR, linking the decision. Keep assumptions marked as assumptions and evidence tied to its revision. Do not change goals merely to make failing behavior pass. Use [documentation reconciliation](../../references/documentation.md) to retain one authority per fact; the verifier reads those records, not a separate interview transcript.
