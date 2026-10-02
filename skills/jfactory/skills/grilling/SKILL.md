---
name: grilling
description: Establish shared goals and verifier criteria during jfactory setup, objective definition, or changes to product, engineering and UI intent. Reuse settled decisions and interview only about unresolved intent.
---

# Matt Pocock's grilling method

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.

# jfactory integration

The method above is Matt Pocock's unchanged [grilling body](../../vendor/mattpocock/skills/grilling/SKILL.md), included here so loading this skill loads the actual method. Apply these jfactory translations to it.

Start from the owner's request and canonical records. During first setup, cover the required [owner interview](../../references/setup.md#2-reconcile-the-foundation). On updates and resumed objectives, carry confirmed answers forward. For each objective, establish the customer outcome, scope, non-goals, affected job goals, observable acceptance criteria and their evidence. If these are already settled, record that and proceed; another confirmation is unnecessary. Ask each consequential unresolved decision with a recommendation; dependent implementation waits for the answer. Existing explicit authorization counts as confirmation within its scope.

Find technical facts from the repository and tools. Upstream's subagent instruction maps to the host's authorized delegation; inspect directly when delegation is unavailable or unnecessary. Use the host's supported question UI and formatting. Continue independent work while answers or investigations are pending.

Write answers and unresolved choices into the existing objective and setup record. When a decision changes standing intent, update the affected project-owned outcome/job documents, engineering sources, UI/UX sources and standards map in the same PR, linking the decision. Keep assumptions marked as assumptions and evidence tied to its revision. Do not change goals merely to make failing behavior pass. Use [documentation reconciliation](../../references/documentation.md) to retain one authority per fact; the verifier reads those records, not a separate interview transcript.
