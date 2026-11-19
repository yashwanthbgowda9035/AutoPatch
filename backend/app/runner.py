"""Opt-in isolated Docker program execution for demo diagnostics.

No submitted source or build command runs on the host. No automatic image pull.
The sandbox reduces risk but is not a complete untrusted-code security boundary.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import sandbox

IMAGES = {
    "python": "python:3.12-alpine",
    "c": "gcc:14",
    "cpp": "gcc:14",
    "java": "eclipse-temurin:21-jdk",
}


def _result(status, language, message, stdout="", stderr="", exit_code=None, phase="not_run", image=None):
    return {
        "status": status, "language": language, "mode": "docker" if phase != "not_run" else "unavailable",
        "message": message, "stdout": stdout[-12000:], "stderr": stderr[-12000:],
        "output": (stdout + ("\n" if stdout and stderr else "") + stderr)[-16000:],
        "exit_code": exit_code, "phase": phase, "image": image,
        "executed": phase in ("completed", "compile_or_run", "timeout"),
    }


def run_code(source: str, language: str) -> dict:
    image = IMAGES.get(language)
    if not image:
        return _result("unavailable", language, "Excel formulas are analyzed statically; this app does not calculate workbook results. No formula was executed.")
    if language == "python":
        check = sandbox.validate_syntax(source)
        if check["status"] != "passed":
            return _result("failed", language, check["message"], stderr=check["output"], phase="syntax", image=image)

    if not shutil.which("docker"):
        return _result("unavailable", language, "Docker executable not found. Start Docker Desktop and check PATH.")
    try:
        info = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=5)
        if info.returncode != 0:
            return _result("unavailable", language, "Docker Engine is not running. Start Docker Desktop.")
        image_check = subprocess.run(["docker", "image", "inspect", image], capture_output=True, text=True, timeout=5)
        if image_check.returncode != 0:
            return _result("unavailable", language, f"Docker image missing. In CMD run: docker pull {image}")
    except (OSError, subprocess.TimeoutExpired):
        return _result("unavailable", language, "Docker did not respond; nothing was executed.")

    java_class = None
    if language == "java":
        match = re.search(r"\bpublic\s+(?:final\s+)?class\s+([A-Za-z_$][\w$]*)", source)
        if match:
            java_class = match.group(1)
        else:
            match = re.search(r"\bclass\s+([A-Za-z_$][\w$]*)", source)
            java_class = match.group(1) if match else "Main"
        # Whitelist a Java identifier before using it in a fixed shell command.
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", java_class):
            return _result("unavailable", language, "Could not safely determine Java class name.")
        filename = f"{java_class}.java"
        cmd = ["sh", "-c", f"javac -d /tmp /workspace/{filename} && java -cp /tmp {java_class}"]
    elif language == "c":
        filename = "main.c"
        cmd = ["sh", "-c", "gcc -Wall -Wextra -o /tmp/autopatch-bin /workspace/main.c && /tmp/autopatch-bin"]
    elif language == "cpp":
        filename = "main.cpp"
        cmd = ["sh", "-c", "g++ -Wall -Wextra -o /tmp/autopatch-bin /workspace/main.cpp && /tmp/autopatch-bin"]
    else:
        filename = "main.py"
        cmd = ["python", "-B", "/workspace/main.py"]

    with tempfile.TemporaryDirectory(prefix="autopatch_run_") as folder:
        workspace = Path(folder)
        workspace.chmod(0o755)
        source_file = workspace / filename
        source_file.write_text(source, encoding="utf-8")
        source_file.chmod(0o644)
        cid_path = workspace / "container.cid"
        command = [
            "docker", "run", "--rm", "--cidfile", str(cid_path),
            "--network", "none", "--read-only", "--pids-limit", "64",
            "--memory", "512m", "--cpus", "0.75", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m,mode=1777",
            "-e", "HOME=/tmp", "-e", "TMPDIR=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{workspace.resolve()}:/workspace:ro", "-w", "/workspace",
            image, *cmd,
        ]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=24, check=False)
        except subprocess.TimeoutExpired:
            if cid_path.exists():
                cid = cid_path.read_text(encoding="utf-8").strip()
                if re.fullmatch(r"[0-9a-f]{12,64}", cid):
                    try:
                        subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=5, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
            return _result("timeout", language, "Execution exceeded 24 seconds. Container cleanup was requested.", stderr="Timed out.", phase="timeout", image=image)
        except OSError as exc:
            return _result("unavailable", language, f"Docker failed to start ({type(exc).__name__}).", image=image)
        ok = process.returncode == 0
        return _result("passed" if ok else "failed", language,
                       "Program exited successfully in Docker." if ok else "Program failed to compile or returned a nonzero exit code inside Docker.",
                       stdout=process.stdout, stderr=process.stderr, exit_code=process.returncode,
                       phase="completed" if ok else "compile_or_run", image=image)
