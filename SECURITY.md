# AutoPatch security boundaries

The full code-execution workflow is a **local-only hackathon prototype**, not a hosted service for untrusted users. The Dockerfile and Render Blueprint support a separate **non-executing public preview** with credentialed and Docker execution features disabled.

- The launcher binds Uvicorn to `127.0.0.1`; the API validates hosts and JSON payload sizes. Keep it local.
- User code is parsed but **never executed on the Python backend host**. Optional execution requires Docker with network disabled, a read-only root, limited resources, reduced privileges and timeouts. Container isolation is not a perfect security boundary.
- The backend does not store uploaded source, CVs, spreadsheets or GitHub tokens in an application database. Temporary Docker workspace files are cleaned up after runs. Docker and GitHub itself may retain logs/commits.
- The GitHub Studio token is sent in the body of a request to the loopback backend and forwarded to GitHub HTTPS; it is not written to disk by AutoPatch. Use a minimally scoped token, and revoke it after use. The website publisher is one-file-only.
- The optional OpenAI integration transmits submitted source to the configured external API only when the user enables it and an API key is configured.
- `.gitignore` blocks common secret files but **cannot detect credentials embedded inside source files**. Always review `git diff --cached` and staged file lists before publishing.
- Uploaded workbook and CV formats have size limits. Avoid processing sensitive or untrusted files on shared machines.
- Security response headers restrict browser resource loading and framing; they are not a substitute for authentication and secure deployment.

Please report vulnerabilities privately to the project maintainer rather than committing secrets or exploit samples to a public repository.

## Safe public-preview mode

Set `AUTOPATCH_PUBLIC_DEMO=1` on hosted deployments. This disables `/api/run` execution, Docker `/api/verify`, `/api/github/publish`, and optional external LLM calls. Static analysis and conservative deterministic repair remain available. The Docker image does not include the Docker CLI and never mounts the host Docker socket. This is a limited demonstration, not an assurance of production-grade protection from all abuse.

The trusted host list is controlled by `AUTOPATCH_ALLOWED_HOSTS`; do not use `*` on public hosts. Add authentication and request rate limiting before exposing sensitive data or costly operations.
