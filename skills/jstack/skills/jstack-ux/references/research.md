# A study that can be resumed and reviewed

Use one study record per app/objective, not one new document per turn. The helper creates `.context/ux/<study>/study.json` for scope/access context, `report.json` for findings and `artifacts/` for captures. Fill the record from observation; its starter fields are not completed research. Existing canonical research documents can own the findings instead, with links to the same artifacts.

At the start, record approved destinations and actions, account role/plan without credentials, target viewports, customer tasks, the decision to inform and a stopping point. Defaults permit observation/navigation only. Scope is an agent instruction, not a browser network filter. Include identity-provider redirects in the access plan when needed.

Maintain this logical model:

- Navigation and entry points, including cross-links and places a user can get lost.
- User-visible objects and relationships, such as a project containing saved items. Label inferred backend structures as unknown.
- For each journey: preconditions, actions, resulting states, persistence/readback, cancellation, retry and exit paths.
- Motion and feedback: what triggered the change, what moved, why it may help, observed timing and reduced-motion behavior.
- Coverage: each relevant journey/state is observed, partial, blocked or not explored. Explain why and the next probe. Role/plan/device variations remain gaps unless checked.

The generated `report.json` has these fields:

```json
{
  "summary": "What was learned and which decision it informs",
  "context": "Date, account role/plan, viewport, app version if exposed",
  "app_map": "Navigation, objects, relationships and cross-journey dependencies",
  "journeys": [{
    "name": "Save an item and find it later",
    "status": "partial",
    "steps": [{
      "action": "Open the saved-items page after reload",
      "observed": "The same item remains visible",
      "evidence": ["artifacts/saved.png", "artifacts/save.webm"]
    }],
    "gaps": "Sharing and deletion not exercised; no permission to change shared data"
  }],
  "findings": [{
    "observed": "The detail panel slides in while the list stays visible",
    "inferred": "This may preserve browsing context",
    "recommendation": "Prototype this only if our task requires comparing multiple items",
    "evidence": ["artifacts/open-panel.webm"]
  }],
  "unknowns": ["No customer usability study; no access to other roles"]
}
```

File references must exist inside `artifacts/`. Use trace links in addition to images/video where replay matters. The renderer rejects missing files and escapes text, but cannot decide if evidence supports a claim. Its output is a private local HTML walkthrough, not a published preview. Captures can include private customer data or session tokens in traces; inspect and redact before sharing. Never put raw competitor sessions in the public jstack repo.

For our own app, identify the code revision/environment and distinguish a component fixture from the actual authenticated journey. An isolated component review can examine focus, layout, loading, errors and motion cheaply. Application review verifies navigation and state across boundaries. Provider/deployed proof remains separate where required. A polished demo does not replace any of these checks.
