# AutoPatch — Autonomous Bug Detection, Repair & Verification

**VS Code + deployment edition:** see [`VSCODE_DEPLOY_GUIDE.md`](VSCODE_DEPLOY_GUIDE.md) for one-folder setup, F5 debugging, quality checks, GitHub push and a safe public-preview deployment. All original animation and 3D-style glass effect assets are unchanged.

**Velocity 5.6 · GitHub Studio · Butter Motion**
Python/FastAPI backend · vanilla JavaScript frontend · local-first hackathon prototype.

AutoPatch analyzes user-provided source, suggests conservative repairs, and separates **static diagnostics**, **proposed patches**, **actual Docker execution**, and **verification results**. Its glass-style interface includes responsive zoom transitions, pointer-reactive controls, and a six-section navigation dock.

## Features

- **Workspace:** Python AST analysis, conservative typo suggestions, Docker runtime traceback diagnostics, and reviewable repair proposals. A failed run is never shown as CLEAN.
- **Languages:** Python primary; narrower heuristic detection/diagnostics for C, C++, Java, and Excel formula text.
- **Verify:** static checks and optional Docker-isolated execution/testing (subject to local images and runtime availability).
- **Excel:** static `.xlsx` formula auditing; does not recalculate formulas.
- **Careers:** compare a supplied CV against requirements in a supplied jobs workbook; does not guarantee hiring outcomes.
- **GitHub Studio:** publish **one source file from the editor** to a new or existing GitHub repository, using a user-provided token for the request only.
- **GitHub full-project upload:** run `PUSH_TO_GITHUB.bat` after creating an empty GitHub repository. This uploads the complete application rather than one editor file.

## Quick start — Windows CMD

1. Install **Python 3.10+**. For isolated execution, install and start **Docker Desktop**.
2. Extract this project and open the `AutoPatch_VSCODE_DEPLOY_READY` folder.
3. In File Explorer, click the address bar, type `cmd`, and press Enter.
4. Run `START_AUTOPATCH.bat` and keep the backend window open.
5. Open **http://127.0.0.1:8015**.

The launcher creates `.venv` and installs `backend/requirements.txt` on first use. The server binds to `127.0.0.1`, not the public internet. No Node.js build step is needed.

## Publish the entire project to GitHub

Read [`README_GITHUB.md`](README_GITHUB.md) and run `PUSH_TO_GITHUB.bat` from the extracted project folder. Git for Windows is required. The `.gitignore` excludes local virtual environments, Python caches, credentials and `.env` files. **Review staged files before approving the upload.**

## Demo

Open Workspace and paste:

```python
print"hello
```

Choose **SUGGEST REPAIR**. The deterministic engine can propose `print("hello")` when the full corrected source parses. Apply the patch, then run it with Docker enabled. For the previously missed runtime typo, use `examples/Student_NameError_BUGGY.py`. For a longer test, use `examples/QuickMart_Buggy_Demo.py`, which intentionally includes both fixable and manual-review defects.

## Runtime repair demonstration

Paste this code into Workspace:

```python
students = [80, 90, 70]
total = sum(students)
average = total / len(student)
print(average)
```
 **ANALYZE + RUN** detects the probable name typo statically; if Docker runs, its `NameError` is also displayed under diagnostics and a patch is proposed automatically. Review the proposal, click **APPLY PATCH**, then **ANALYZE + RUN** again. A proposed patch is not marked verified until the program and appropriate tests actually pass.

## Tests

```cmd
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

Or run `RUN_QUALITY_GATE.bat` from the project folder. The `PUSH_TO_GITHUB.bat` script also runs this gate before pushing. GitHub Actions runs Python tests on Windows and Linux (Python 3.11/3.12) and checks JavaScript syntax on each push/PR.

See [`EVALUATION.md`](EVALUATION.md) for the test matrix, known limitations, and honest evaluation claims.

## Architecture and limits

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for API routes, Docker constraints, and honest capability boundaries. Docker provides layered isolation but is not a perfect security boundary; do not expose this prototype as a public arbitrary-code-execution service. The optional AI repair path requires a separately configured `OPENAI_API_KEY` and explicit opt-in; it is **not a locally trained model**. No API keys or GitHub tokens are included in this repository.

**Project scope:** 24-hour hackathon demonstration; review proposed patches before applying or publishing.
