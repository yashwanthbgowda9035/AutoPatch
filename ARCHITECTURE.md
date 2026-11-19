# AutoPatch Velocity 5.6 — Architecture and boundaries

```text
Browser: HTML + CSS + vanilla JavaScript (localhost:8015)
  ├── Experience: animated landing and accessible motion toggle
  ├── Workspace: source editor → /api/detect, /api/analyze, /api/repair, /api/run
  ├── Verify: /api/verify → static checks / optional Docker tests
  ├── Excel: /api/workbook/analyze → static XLSX formula inspection
  ├── Careers: /api/career/match → user-supplied CV and job criteria
  └── GitHub: /api/github/publish → one-file publish via GitHub REST API

FastAPI backend, 127.0.0.1:8015
  ├── autodetect.py: weighted language/extension hints
  ├── engine.py: Python AST/token diagnostics + conservative patch proposals
  ├── runtime_diagnostics.py: traceback parsing and scope-aware name typo suggestions
  ├── multilang.py: limited C/C++/Java/Excel heuristics
  ├── runner.py: optional Docker source execution
  ├── sandbox.py: optional Docker Python unittest execution
  ├── workbook.py: Office Open XML formula inspection
  ├── career.py: CV/job requirement matching
  ├── llm.py: optional external LLM repair (requires configured API key)
  └── github_publish.py: GitHub API repo creation and file contents upload

Git for Windows (separate from the web dashboard)
  └── PUSH_TO_GITHUB.bat: commits and pushes the ENTIRE project repository
```

## Repair and execution

- Syntax analysis and patch generation do not imply successful execution.
- Simple standalone Python 3 print-literal syntax such as `print"hello` can be repaired to `print("hello")` only if the entire corrected source parses.
- Python `NameError` from a failed Docker run is parsed, shown in diagnostics, and used to propose a minimal replacement **only** when a similar name was previously bound in the same lexical scope. Static module-scope typo hints are also supported.
- A patch is **proposed**, not verified, until it is applied and the code is rerun/tested. No unsafe guess is made for ambiguous names, dynamic namespaces, or other unsupported runtime errors.
- Other rules are deliberately conservative; ambiguous issues may require manual review.
- Python execution/verification runs only when Docker and the needed images are available.
- Docker uses no network, a read-only filesystem, reduced privileges and resource limits. This is **defense in depth, not perfect isolation**. Never expose the local prototype to untrusted public traffic.

## Frontend performance

- `frontend/assets/butter.css`: short ~390ms compositor-oriented zoom transitions, modest blur.
- `frontend/assets/sport-glass.js`: frosted dock previews, magnetic buttons, pointer highlights.
- `frontend/assets/github.css` and `github.js`: single-file repository publisher UI.
- Responsive layout, keyboard focus and reduced-motion fallbacks.

## Limits and data handling

- C/C++/Java diagnostics are heuristics, not complete compiler frontends.
- XLSX audit does not recalculate formulas; existing cached values may be shown.
- CV/job matching uses only the supplied documents; it is not a hiring prediction.
- Optional LLM use is opt-in and does not involve model training or fine-tuning.
- GitHub Studio sends the supplied token to the local FastAPI backend for HTTPS requests to GitHub; it is not persisted by the app. The dashboard publishes one file per action.
- `.gitignore` excludes common secrets and virtual environments, but developers must still review staged files.
