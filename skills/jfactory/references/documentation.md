# Reconcile documentation without losing decisions

Use during setup, when instructions conflict, and when implementation changes a documented fact. Cleanup belongs in the current task or adoption PR. Preserve unrelated working changes and do not rewrite the managed skill bundle or vendored pstack sources.

## Find the authority for each fact

Inventory root and nested agent files, host entry points, project-owned skills, README/onboarding, product/architecture documents, task/status records and operational runbooks. Search for old skill paths, renamed repositories, draft/merge/deploy policies, obsolete commands and duplicated feature status. Trace links, scripts and CI consumers before moving a document. Exclude dependencies, generated assets and private browser profiles.

For each active fact, choose one existing canonical home. Distinguish:

- Owner decisions and hypotheses, with their source when available.
- Implementation facts, supported by current code/configuration.
- Runtime claims, supported by evidence with a revision and environment.
- Historical decisions and evidence, which remain true about their original context.

A later file date is not authority. A product requirement can be valid while implementation falls short. Resolve technical facts through inspection or checks; ask only where conflicting intent or authorization cannot be determined. Never overwrite a requirement to match the code or promote an unchecked feature to verified.

## Make a reviewable cleanup

| Finding | Action |
| --- | --- |
| Accurate active document | Keep it and link to it |
| Stale command, path or implementation claim | Correct it using current evidence; mark unverified runtime claims explicitly |
| Duplicate active guidance | Move unique current content into the canonical home, update callers, then remove the duplicate or retain a short pointer where external links need it |
| Superseded plan/status | Preserve unique decisions, mark it historical or archive it, and remove it from active instruction paths |
| Conflicting owner intent | Record the competing sources and the precise decision needed; continue unrelated cleanup |
| Generated, managed or vendored file | Update its source or supported installer; keep project policy in project-owned records |

For removed or consolidated material, summarize the old path, new home and reason in the adoption task or PR. Git preserves committed history, but protect uncommitted unique content before deleting anything. Do not mass-delete by filename, age or a "stale" keyword. Preserve historical receipts and mark superseded proof stale instead of changing its original identity.

Fix relative links, instructions that load moved files, task references and known external entry points. Verify relevant links exist and referenced commands still exist; execute commands when needed to support their claims. Search again for the contradictions you resolved. Keep unresolved items visible rather than calling the whole documentation tree current.

## When a document and the code disagree

Decide which one is wrong before changing either:

- **The document is out of date.** The code reflects an intended change: an owner decision, an agreed objective or a merged PR that says so. Update the document in the same change and link that decision.
- **The product broke.** The document still states the intent, and the code no longer meets it. Report it as a defect or an objective, with the document and the observed behavior as evidence. Do not edit the document to match; that hides a regression from every later check.
- **Unclear.** Record both sources and the decision needed, and ask the owner. Keep the document unchanged until they answer.

Outcome and standards documents (`outcomes/`, `.jfactory/standards.md`) are the sources verifiers check against, so an edit to one always gets an independent review of which case it is.

## Keep it current during work

Use [grilling](../skills/grilling/SKILL.md) when a change or feedback reveals unresolved product, engineering or UI/UX intent, and [show-me](../skills/show-me/SKILL.md) when the owner needs to understand the change or choice. Carry the resulting decisions into the affected sources and job goals before verification; preserve settled answers and mark any consequential unresolved intent as a blocker for dependent work.

Update a fact in its canonical home in the same change that alters it. Feature status should distinguish proposed, implemented, verified at a specific scope/revision, and owner-accepted. Link to evidence and the task/PR instead of copying logs. Keep current next steps in one task record; archive completed task context according to the repo's convention.

AGENTS.md remains the short entry point with product brief, system map, feature/status map and agent instructions. Details belong at the linked homes. A new document needs a distinct purpose and a discoverable link; another status report for the same task does not.
