# AutoPatch Velocity 5.6 — Evaluation and reproducibility

## What is implemented

- FastAPI backend serving a responsive single-page HTML/CSS/vanilla-JS interface.
- Python AST/token analysis with narrow, deterministic fixes; optional external LLM proposals **only** when an API key is configured and explicitly requested.
- Conservative undefined-variable typo hints, including the previously missed `student` vs `students` error.
- Docker execution for Python/C/C++/Java when their local images are available; Docker-based Python unittest verification.
- Static XLSX formula auditing; local CV/job-sheet matching; single-file GitHub Studio publishing; Git-based full-project upload.
- CSP, local trusted-host restriction, bounded API payloads, secret-file exclusions, reduced-motion UI support.

## Exact reproduction of the reported NameError

1. Run `START_AUTOPATCH.bat`; visit `http://127.0.0.1:8015`.
2. Open Workspace; upload `examples/Student_NameError_BUGGY.py`.
3. Click **ANALYZE + RUN**. Static analysis reports a possible undefined-name typo. If Docker is ready, the runtime output reports a `NameError`, and the diagnostics badge becomes **RUNTIME ERROR**.
4. The proposed patch replaces `student` with `students` on the affected line. Click **APPLY PATCH**.
5. Click **ANALYZE + RUN** again and use Verify with meaningful unittest cases. A syntax PASS alone does not establish behavioral correctness.

## Quality gates

- `RUN_QUALITY_GATE.bat` — installs test dependencies, runs Python pytest, and checks JS syntax if Node.js is present.
- `cd backend && python -m pytest tests -q` — backend API, engine, repair, safety, file workflows, GitHub mocks and UI asset checks.
- `python -m compileall -q backend/app backend/tests` — syntax check of Python application and tests.
- `node --check frontend/assets/cinema.js` (and each other frontend JS file) — syntax only.
- `python qa_browser_smoke.py` — optional **offline** Playwright Chromium smoke test; real frontend and FastAPI analysis/repair responses, simulated Docker traceback. Requires Playwright and Chromium.
- `.github/workflows/tests.yml` — CI on push and pull request, Linux and Windows Python 3.11/3.12, plus Node JS syntax checks.

## What is *not* claimed

- No guarantee of zero bugs or that an external AI evaluator will find no defects.
- Static syntax validation is **not** runtime or logic verification.
- Passing one execution does **not** prove full functional correctness.
- Docker execution was not available in the build environment; actual Windows Docker execution should be checked on the target PC.
- The deterministic repair rules cannot solve every `NameError`, data-flow issue, algorithmic error or dependency problem. Ambiguous cases intentionally require review.
- C/C++/Java diagnostics are limited heuristics, not comprehensive static analysis.
- XLSX formula audits do not recalculate workbooks; CV matching is not a hiring eligibility decision.
- GitHub Studio publishes one file per action. Use Git and `PUSH_TO_GITHUB.bat` to publish the complete application.
- The local Docker sandbox is defense-in-depth, **not** a hardened public multi-tenant execution service. Do not expose it to the internet.

## Evaluation checklist

A strong evaluation should test correct input, syntax errors, runtime errors, unsupported cases, file-size limits, Docker absence, token/API failures, and UI responsiveness. Review actual `pytest` and GitHub Actions results rather than relying on marketing claims or screenshots alone.

## VS Code and hosted-preview edition

The complete project includes `.vscode/` debugger/tasks, a Windows setup script, a safe non-executing Docker image, `compose.yaml`, and a Render Blueprint. The public preview explicitly blocks Docker execution, GitHub publishing and external LLM requests. Dedicated API tests verify these controls. This edition preserves all existing frontend assets byte-for-byte. See `VSCODE_DEPLOY_GUIDE.md`.
