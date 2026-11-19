"""AutoPatch local API and frontend server."""
from __future__ import annotations

from pathlib import Path
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import engine, llm, sandbox, multilang, career, autodetect, runner, workbook, db
from .samples import SAMPLES
from .github_publish import PublishRequest, publish as github_publish

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def public_demo_mode() -> bool:
    """Public preview deliberately excludes code execution and credentialed actions."""
    return os.getenv("AUTOPATCH_PUBLIC_DEMO", "0").strip().lower() in {"1", "true", "yes", "on"}


def trusted_hosts() -> list[str]:
    """Permit explicitly configured hosts; loopback only unless deployment opts in."""
    raw = os.getenv("AUTOPATCH_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    hosts = [host.strip() for host in raw.split(",") if host.strip()]
    return hosts or ["localhost", "127.0.0.1", "testserver"]


app = FastAPI(
    title="AutoPatch API",
    version="5.6.0",
    description="Auto-detected Python/C/C++/Java/Excel diagnostics, Docker outputs, XLSX auditing and local CV-to-job matching.",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts())
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8015", "http://127.0.0.1:8015"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/assets", StaticFiles(directory=str(FRONTEND / "assets")), name="assets")
app.mount("/examples", StaticFiles(directory=str(FRONTEND.parent / "examples")), name="examples")


class CodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    filename: str = Field(default="untitled", max_length=100)
    use_ai: bool = False
    runtime_stderr: str = Field(default="", max_length=12000)
    runtime_exit_code: int | None = Field(default=None, ge=-255, le=255)
    language: Literal["auto", "python", "c", "cpp", "java", "excel"] = "auto"

    @field_validator("filename")
    @classmethod
    def python_filename(cls, value: str) -> str:
        if (
            value != "untitled"
            and not value.lower().endswith(
                (".py", ".c", ".cpp", ".cc", ".cxx", ".java", ".formula", ".txt")
            )
        ) or "/" in value or "\\" in value or any(
            c in value for c in (":", "<", ">", "|", "?", "*", "\0")
        ) or value.startswith("."):
            raise ValueError("filename must be a supported source filename without path separators")
        return value


class VerifyRequest(BaseModel):
    language: Literal["auto", "python", "c", "cpp", "java", "excel"] = "auto"
    filename: str = Field(default="untitled", max_length=100)
    code: str = Field(min_length=1, max_length=20000)
    tests: str = Field(default="", max_length=12000)
    mode: Literal["static", "docker"] = "static"


class RunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    filename: str = Field(default="untitled", max_length=100)
    language: Literal["auto", "python", "c", "cpp", "java", "excel"] = "auto"


class WorkbookRequest(BaseModel):
    filename: str = Field(min_length=5, max_length=120)
    data_base64: str = Field(min_length=8, max_length=workbook.MAX_WORKBOOK_BYTES * 4 // 3 + 100)


class CareerRequest(BaseModel):
    cv_filename: str = Field(min_length=5, max_length=120)
    cv_base64: str = Field(min_length=8, max_length=career.MAX_FILE_BYTES * 4 // 3 + 100)
    jobs_filename: str = Field(min_length=5, max_length=120)
    jobs_base64: str = Field(min_length=8, max_length=career.MAX_FILE_BYTES * 4 // 3 + 100)


class HistoryCreateRequest(BaseModel):
    filename: str = Field(default="untitled", max_length=100)
    language: str = Field(default="python", max_length=20)
    action: str = Field(default="run", max_length=30)
    status: str = Field(default="completed", max_length=30)
    code: str = Field(min_length=1, max_length=20000)
    stdout: str = Field(default="", max_length=12000)
    stderr: str = Field(default="", max_length=12000)
    exit_code: int | None = Field(default=None, ge=-255, le=255)
    repaired_code: str = Field(default="", max_length=20000)
    issues_count: int = Field(default=0, ge=0)
    ai_used: bool = False


class SnippetCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=100)
    language: str = Field(default="python", max_length=20)
    code: str = Field(min_length=1, max_length=20000)
    tests: str = Field(default="", max_length=12000)
    description: str = Field(default="", max_length=300)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "product": "AutoPatch", "version": "5.6.0"}


@app.get("/api/status", tags=["Health"])
def status():
    return {
        "backend": "online",
        "version": "5.6.0",
        "engine": "Auto detection + Python AST + C/C++/Java/Excel heuristics",
        "ai_configured": llm.is_configured() and not public_demo_mode(),
        "ai_provider": None if public_demo_mode() else llm.get_provider(),
        "docker": (
            {"available": False, "message": "Docker execution is disabled in public preview."}
            if public_demo_mode()
            else sandbox.docker_status()
        ),
        "db_status": "online",
        "max_code_chars": 20000,
        "languages": ["python", "c", "cpp", "java", "excel"],
        "cv_excel_matching": True,
        "automatic_language_detection": True,
        "docker_program_output": not public_demo_mode(),
        "github_publishing": not public_demo_mode(),
        "public_demo": public_demo_mode(),
        "xlsx_formula_audit": True,
    }


@app.get("/api/samples", tags=["Demo"])
def samples():
    return {"samples": SAMPLES}


@app.get("/api/history", tags=["History"])
def get_history(limit: int = 50):
    return {"history": db.get_history(limit=limit)}


@app.post("/api/history", tags=["History"])
def add_history(item: HistoryCreateRequest):
    record = db.record_history(
        filename=item.filename,
        language=item.language,
        action=item.action,
        status=item.status,
        code=item.code,
        stdout=item.stdout,
        stderr=item.stderr,
        exit_code=item.exit_code,
        repaired_code=item.repaired_code,
        issues_count=item.issues_count,
        ai_used=item.ai_used,
    )
    return {"status": "recorded", "record": record}


@app.delete("/api/history", tags=["History"])
def delete_history():
    count = db.clear_history()
    return {"status": "cleared", "deleted_count": count}


@app.get("/api/snippets", tags=["Snippets"])
def get_snippets():
    saved = db.get_snippets()
    if not saved:
        for s in SAMPLES:
            db.save_snippet(
                snippet_id=s["id"],
                title=s["title"],
                language=s.get("language", "python"),
                code=s["code"],
                tests=s.get("tests", ""),
                description=s.get("description", ""),
            )
        saved = db.get_snippets()
    return {"snippets": saved}


@app.post("/api/snippets", tags=["Snippets"])
def create_snippet(item: SnippetCreateRequest):
    saved = db.save_snippet(
        snippet_id=item.id,
        title=item.title,
        language=item.language,
        code=item.code,
        tests=item.tests,
        description=item.description,
    )
    return {"status": "saved", "snippet": saved}


@app.delete("/api/snippets/{snippet_id}", tags=["Snippets"])
def remove_snippet(snippet_id: str):
    success = db.delete_snippet(snippet_id)
    if not success:
        raise HTTPException(status_code=404, detail="Snippet not found.")
    return {"status": "deleted", "id": snippet_id}


def _language(request):
    detected = autodetect.detect(request.code, getattr(request, "filename", "untitled"))
    language = detected["language"] if request.language == "auto" else request.language
    if request.language != "auto":
        detected = {
            **detected,
            "language": language,
            "reason": "Explicit API language override",
            "tentative": False,
            "confidence": 1.0,
        }
    return language, detected


@app.post("/api/detect", tags=["Engine"])
def detect(request: CodeRequest):
    return _language(request)[1]


@app.post("/api/analyze", tags=["Engine"])
def analyze(request: CodeRequest):
    language, detected = _language(request)
    result = (
        engine.analyze(request.code)
        if language == "python"
        else multilang.analyze(request.code, language)
    )
    return {**result, "detected_language": language, "detection": detected}


@app.post("/api/repair", tags=["Engine"])
def repair(request: CodeRequest):
    language, detected = _language(request)
    if language != "python":
        rep = multilang.repair(request.code, language)
        db.record_history(
            filename=request.filename,
            language=language,
            action="repair",
            status="suggested" if rep.get("changed") else "no_patch",
            code=request.code,
            repaired_code=rep.get("repaired_code", ""),
            issues_count=len(rep.get("remaining_issues", [])),
            ai_used=False,
        )
        return {**rep, "detected_language": language, "detection": detected}

    result = engine.repair(request.code, request.runtime_stderr, request.runtime_exit_code)
    result["ai_used"] = False
    result["ai_message"] = "AI not requested; deterministic repair was used."
    if request.use_ai and public_demo_mode():
        result["ai_message"] = (
            "External AI requests are disabled in public preview. Deterministic repair was used."
        )
    elif request.use_ai:
        if not llm.is_configured():
            result["ai_message"] = (
                "AI was requested but OPENAI_API_KEY is not set (set GEMINI_API_KEY or OPENAI_API_KEY); deterministic repair was used."
            )
        else:
            suggestion, message = llm.suggest_code(result["repaired_code"])
            result["ai_message"] = message
            if suggestion is not None and suggestion != result["repaired_code"]:
                from difflib import unified_diff

                result["repaired_code"] = suggestion
                result["changed"] = suggestion != request.code
                result["ai_used"] = True
                result["repair_mode"] = "deterministic_plus_optional_ai"
                result["remaining_issues"] = engine.analyze(suggestion)["issues"]
                result["syntax_valid"] = True
                result["validation_message"] = (
                    "AI proposal passed syntax checks. Review diff and verify functionality before accepting."
                )
                result["unified_diff"] = "\n".join(
                    unified_diff(
                        request.code.splitlines(),
                        suggestion.splitlines(),
                        fromfile="before.py",
                        tofile="after.py",
                        lineterm="",
                    )
                )

    db.record_history(
        filename=request.filename,
        language=language,
        action="repair",
        status="suggested" if result.get("changed") else "no_patch",
        code=request.code,
        repaired_code=result.get("repaired_code", ""),
        issues_count=len(result.get("remaining_issues", [])),
        ai_used=result.get("ai_used", False),
    )
    return {**result, "detected_language": language, "detection": detected}


@app.post("/api/verify", tags=["Testing"])
def verify(request: VerifyRequest):
    language, detected = _language(request)
    if request.mode == "static":
        if language == "python":
            return {**sandbox.validate_syntax(request.code), "detected_language": language}
        report = multilang.analyze(request.code, language)
        critical_issues = [
            i
            for i in report["issues"]
            if i["severity"] in ("critical", "high")
            or i["rule"].startswith(("ML-BRACE", "XL-REF", "XL-DIV"))
        ]
        if critical_issues:
            err_text = "\n".join(
                f"Line {i.get('line', '?')}: {i['title']} - {i['detail']}"
                for i in critical_issues
            )
            return {
                "status": "failed",
                "mode": "static",
                "exit_code": None,
                "message": f"{language.upper()} static check flagged {len(critical_issues)} issue(s).",
                "output": f"Static analysis: FAIL\n{err_text}",
                "detected_language": language,
            }
        return {
            "status": "passed",
            "mode": "static",
            "exit_code": None,
            "message": f"{language.upper()} static syntax and structure checks passed.",
            "output": f"Static analysis: PASS\nLanguage: {language}\nNo code was executed.",
            "detected_language": language,
        }

    if language != "python":
        return {
            "status": "unavailable",
            "mode": request.mode,
            "exit_code": None,
            "output": "",
            "message": "Python only: this endpoint verifies unit tests. C/C++/Java may be compiled/run using /api/run when their Docker images are available; Excel uses static analysis only.",
        }
    if public_demo_mode():
        return {
            "status": "unavailable",
            "mode": "docker",
            "exit_code": None,
            "message": "Docker tests are disabled in the public preview. Run locally to verify behavior.",
            "output": "No code was executed.",
            "detected_language": language,
        }
    return {**sandbox.run_isolated_tests(request.code, request.tests), "detected_language": language}


@app.post("/api/run", tags=["Testing"])
def run_program(request: RunRequest):
    language, detected = _language(request)
    if public_demo_mode():
        return {
            "status": "unavailable",
            "language": language,
            "mode": "unavailable",
            "message": "Program execution is disabled in the public preview. Run AutoPatch locally with Docker Desktop.",
            "stdout": "",
            "stderr": "",
            "output": "No code was executed.",
            "exit_code": None,
            "phase": "not_run",
            "image": None,
            "executed": False,
            "runtime_issues": [],
            "detected_language": language,
            "detection": detected,
        }
    result = runner.run_code(request.code, language)
    if language == "python" and result["status"] == "failed" and result.get("exit_code") is not None:
        result["runtime_issues"] = engine.runtime_issues(
            request.code, result.get("stderr", ""), result["exit_code"]
        )
    else:
        result["runtime_issues"] = []

    db.record_history(
        filename=request.filename,
        language=language,
        action="run",
        status=result.get("status", "completed"),
        code=request.code,
        stdout=result.get("stdout", ""),
        stderr=result.get("stderr", ""),
        exit_code=result.get("exit_code"),
        issues_count=len(result.get("runtime_issues", [])),
    )
    return {**result, "detected_language": language, "detection": detected}


@app.post("/api/workbook/analyze", tags=["Excel"])
def analyze_workbook(request: WorkbookRequest):
    import base64
    import binascii

    if not request.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Upload an XLSX workbook only.")
    try:
        payload = base64.b64decode(request.data_base64, validate=True)
        return workbook.audit_xlsx(payload)
    except (ValueError, zipfile.BadZipFile, ET.ParseError, binascii.Error) as exc:
        raise HTTPException(
            status_code=422, detail=f"Could not read workbook: {str(exc)[:180]}"
        ) from exc


@app.post("/api/career/match", tags=["Career"])
def career_match(request: CareerRequest):
    """No files persisted. CV + user-supplied spreadsheet processed locally in memory."""
    if not request.cv_filename.lower().endswith(
        (".txt", ".pdf", ".docx")
    ) or not request.jobs_filename.lower().endswith((".xlsx", ".csv")):
        raise HTTPException(
            status_code=422, detail="Upload a CV (.txt/.pdf/.docx) and job listings (.xlsx/.csv)."
        )
    try:
        cv_data = career.decode_file(request.cv_base64)
        jobs_data = career.decode_file(request.jobs_base64)
        return career.analyze_files(cv_data, request.cv_filename, jobs_data, request.jobs_filename)
    except (ValueError, zipfile.BadZipFile, KeyError, ImportError, ET.ParseError) as exc:
        raise HTTPException(
            status_code=422, detail=f"File could not be processed: {str(exc)[:230]}"
        ) from exc


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(FRONTEND / "assets" / "favicon.svg", media_type="image/svg+xml")


@app.post("/api/github/publish", tags=["GitHub"])
def publish_github(request: PublishRequest):
    if public_demo_mode():
        raise HTTPException(
            status_code=403,
            detail="GitHub publishing is disabled in public preview. Use the local dashboard or Git CLI.",
        )
    return github_publish(request)
