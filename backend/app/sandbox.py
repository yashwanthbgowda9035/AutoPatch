"""Optional, constrained Docker test runner; never execute user snippets on host."""
from __future__ import annotations

import ast
import shutil
import subprocess
import tempfile
from pathlib import Path

IMAGE = "python:3.12-alpine"


def docker_status() -> dict:
    if not shutil.which("docker"):
        return {"available": False, "message": "Docker executable not found. Static validation and automatic repair still work; Docker is optional."}
    try:
        info = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                              capture_output=True, text=True, timeout=4, check=False)
        if info.returncode != 0:
            return {"available": False, "message": "Docker Desktop is not running or not accessible. Start Docker Desktop to run isolated tests."}
        image = subprocess.run(["docker", "image", "inspect", IMAGE],
                               capture_output=True, text=True, timeout=4, check=False)
        if image.returncode != 0:
            return {"available": False, "message": "Docker image is missing. Run: docker pull python:3.12-alpine"}
        return {"available": True, "message": "Docker sandbox ready for isolated unittest execution."}
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "message": "Docker did not respond. Static validation remains available."}


def validate_syntax(source: str) -> dict:
    try:
        ast.parse(source)
        return {"status": "passed", "mode": "static", "exit_code": None,
                "message": "Python syntax is valid. This does NOT prove tests pass or the code is logically correct.",
                "output": "AST parse: PASS\nNo code was executed."}
    except SyntaxError as exc:
        return {"status": "failed", "mode": "static", "exit_code": None,
                "message": f"Syntax error on line {exc.lineno}: {exc.msg}",
                "output": f"AST parse: FAIL\nLine {exc.lineno}, column {exc.offset}: {exc.msg}"}


def run_isolated_tests(source: str, tests: str) -> dict:
    syntax = validate_syntax(source)
    if syntax["status"] != "passed":
        syntax["mode"] = "docker"
        return syntax
    if not tests.strip():
        return {"status": "unavailable", "mode": "docker", "exit_code": None,
                "message": "Add a Python unittest test suite before requesting a sandbox run.", "output": ""}
    try:
        ast.parse(tests)
    except SyntaxError as exc:
        return {"status": "failed", "mode": "docker", "exit_code": None,
                "message": f"Test suite syntax error on line {exc.lineno}: {exc.msg}", "output": ""}
    availability = docker_status()
    if not availability["available"]:
        return {"status": "unavailable", "mode": "docker", "exit_code": None,
                "message": availability["message"], "output": "No code was executed on the host."}

    with tempfile.TemporaryDirectory(prefix="autopatch_tests_") as temp:
        workspace = Path(temp)
        workspace.chmod(0o755)  # Docker runs as an unprivileged user; allow read-only traversal.
        container_id_file = workspace / "container.cid"
        # Fixed filenames prevent path traversal and importing unintended host modules.
        (workspace / "main.py").write_text(source, encoding="utf-8")
        (workspace / "test_main.py").write_text(tests, encoding="utf-8")
        command = [
            "docker", "run", "--rm", "--cidfile", str(container_id_file), "--network", "none", "--read-only", "--pids-limit", "64",
            "--memory", "192m", "--cpus", "0.5", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m",
            "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/workspace",
            "-v", f"{workspace.resolve()}:/workspace:ro", "-w", "/workspace",
            IMAGE, "python", "-B", "-m", "unittest", "discover", "-s", "/workspace",
            "-p", "test_*.py", "-v",
        ]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=18, check=False)
        except subprocess.TimeoutExpired:
            # Killing the Docker CLI alone may leave a container running; stop it explicitly.
            if container_id_file.exists():
                container_id = container_id_file.read_text(encoding="utf-8").strip()
                if container_id and all(ch in "0123456789abcdef" for ch in container_id):
                    try:
                        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True,
                                       text=True, timeout=4, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
            return {"status": "timeout", "mode": "docker", "exit_code": None,
                    "message": "Test execution exceeded the 18-second limit. AutoPatch requested sandbox termination.", "output": "Execution timed out."}
        except OSError as exc:
            return {"status": "unavailable", "mode": "docker", "exit_code": None,
                    "message": f"Docker could not start: {type(exc).__name__}.", "output": ""}
        output = (proc.stdout + ("\n" if proc.stdout and proc.stderr else "") + proc.stderr)[-15000:]
        if proc.returncode == 0 and "Ran 0 tests" in output:
            return {"status": "unavailable", "mode": "docker", "exit_code": proc.returncode,
                    "message": "No unittest tests were discovered; no behavioral verification occurred.",
                    "output": output}
        return {"status": "passed" if proc.returncode == 0 else "failed", "mode": "docker",
                "exit_code": proc.returncode,
                "message": "All sandbox unit tests passed." if proc.returncode == 0 else "One or more unit tests failed (or Docker returned an error).",
                "output": output}
