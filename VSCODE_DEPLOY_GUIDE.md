# AutoPatch — VS Code, GitHub and safe deployment guide

This folder contains the **complete AutoPatch 5.6 application**, plus VS Code setup, debugging, tests and public-preview deployment. All existing animation, layout and pointer-effect assets were retained unchanged; the GitHub dashboard JavaScript additionally disables credential entry in public-preview mode.

## 1. Open in VS Code (Windows)

1. Install Python 3.10+, VS Code, and the VS Code **Python** and **Python Debugger** extensions.
2. Extract the ZIP, then **File → Open Folder** → `AutoPatch_VSCODE_DEPLOY_READY`.
3. In VS Code select **Terminal → New Terminal**. If it opens PowerShell, the `.bat` commands below still work; use `cmd` to switch to Command Prompt if preferred.
4. Run `SETUP_VSCODE.bat` once. This creates `.venv` and installs backend + test dependencies.
5. Run `RUN_VSCODE.bat`, or press **F5** and choose **AutoPatch: Debug FastAPI (local)**.
6. Open <http://127.0.0.1:8015> (API docs: <http://127.0.0.1:8015/docs>).
7. Start Docker Desktop and run `docker pull python:3.12-alpine` if you want Python program execution and Docker-based tests. For C/C++/Java, additional images are required; see `ARCHITECTURE.md`.

**Important:** The website is served directly by FastAPI. There is **no npm install or Vite build** needed. Do not double-click `frontend/index.html` as a file: API calls need the backend server.

## 2. Debug and test

- **F5** starts the Python debugger. Breakpoints in `backend/app/*.py` will work.
- **Terminal → Run Task** exposes setup, run, quality gate, Docker preview, and GitHub upload.
- Run `RUN_QUALITY_GATE.bat` before uploading to GitHub. Node.js is optional locally; GitHub Actions checks JS syntax in CI.
- Test the runtime NameError fix using `examples/Student_NameError_BUGGY.py` in Workspace.

## 3. Safe Docker preview (local)

With Docker Desktop running, execute `DEPLOY_PREVIEW.bat`, then visit <http://127.0.0.1:8016>.

This builds `Dockerfile` using `compose.yaml`. **Public-preview mode intentionally disables user-code execution, Docker tests, GitHub token publishing and external AI requests.** Static analysis, deterministic repair, Excel auditing, CV/job matching and all UI animations remain available. The container does **not** mount the Docker socket.

Stop with `Ctrl+C` then `docker compose down`.

## 4. GitHub push (complete repository)

Create an empty GitHub repository (do not initialize with a README), then run `PUSH_TO_GITHUB.bat` and paste its HTTPS URL when asked. Review the staged file list before confirming. `.env`, `.venv`, caches and credentials are excluded. The `.vscode` folder **is included** so evaluators can reproduce the setup. GitHub Studio in the website only publishes a single source file; use the script for the whole project.

## 5. Deploy to Render (public preview)

1. Push this project to GitHub.
2. Sign in to Render and create a **Web Service** from the repository, choosing **Docker** as the runtime. Render may also support importing the included `render.yaml` Blueprint.
3. Use the repository root as the Docker build context. The Dockerfile is at `./Dockerfile`.
4. Configure environment variables: `AUTOPATCH_PUBLIC_DEMO=1` and `AUTOPATCH_ALLOWED_HOSTS=*.onrender.com,localhost,127.0.0.1`. Do **not** set `OPENAI_API_KEY` on a public preview.
5. Deploy. The container starts Uvicorn on the `PORT` supplied by the host (or 8015 locally); check `/health`.
6. Test `/api/status` and confirm `public_demo: true`, `docker.available: false`, and `github_publishing: false`.

Cloud providers may change plan options and deployment steps. This is a **non-executing public preview**, not a hardened multi-tenant code runner. Keep real code execution on your own trusted local machine with Docker Desktop, or design a separate authenticated isolated runner before enabling it for remote users.

## 6. Preserved visual design

The original `frontend/index.html`, CSS, and motion-effect scripts are unchanged: dock hover previews, magnetic buttons, sporty zoom-and-blur transitions, glass panels, pointer glow, particle effects and responsive layouts remain intact. Only the GitHub dashboard logic adds a public-preview safety guard.

## Known limitations

- Deterministic repairs do not fix all bugs; syntax validation is not proof of correct behavior.
- Docker program execution requires Docker Desktop and pre-pulled images on the local host.
- A publicly reachable app must have authentication, rate limits and abuse controls before enabling expensive or credentialed features.
- `AUTOPATCH_ALLOWED_HOSTS` is a comma-separated list of trusted hostnames (no scheme or port); the default only allows localhost.
- Never commit tokens, API keys or private CV data. See `SECURITY.md` and `EVALUATION.md`.
