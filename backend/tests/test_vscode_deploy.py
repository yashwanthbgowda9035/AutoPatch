"""VS Code/deployment regression checks without Docker or internet access."""
from __future__ import annotations
import os
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app, trusted_hosts

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def test_default_trusted_hosts_local_only():
    with patch.dict(os.environ, {"AUTOPATCH_ALLOWED_HOSTS": ""}):
        assert trusted_hosts() == ["localhost", "127.0.0.1", "testserver"]


def test_configured_trusted_hosts():
    with patch.dict(os.environ, {"AUTOPATCH_ALLOWED_HOSTS": "*.onrender.com, localhost,127.0.0.1"}):
        assert trusted_hosts() == ["*.onrender.com", "localhost", "127.0.0.1"]


def test_public_preview_status_disables_dangerous_features():
    with patch.dict(os.environ, {"AUTOPATCH_PUBLIC_DEMO": "1"}):
        with patch("app.sandbox.docker_status", side_effect=AssertionError("must not query Docker")):
            response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["public_demo"] is True
    assert data["docker"]["available"] is False
    assert data["github_publishing"] is False
    assert data["ai_configured"] is False


def test_public_preview_run_never_calls_runner():
    with patch.dict(os.environ, {"AUTOPATCH_PUBLIC_DEMO": "1"}):
        with patch("app.runner.run_code", side_effect=AssertionError("must not run")):
            response = client.post("/api/run", json={"code": "print('hello')", "language": "python"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["executed"] is False
    assert data["runtime_issues"] == []


def test_public_preview_docker_tests_never_execute():
    with patch.dict(os.environ, {"AUTOPATCH_PUBLIC_DEMO": "1"}):
        with patch("app.sandbox.run_isolated_tests", side_effect=AssertionError("must not run")):
            response = client.post("/api/verify", json={"code": "x=1", "tests": "import unittest", "mode": "docker"})
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert "No code was executed" in response.json()["output"]


def test_public_preview_static_syntax_still_available():
    with patch.dict(os.environ, {"AUTOPATCH_PUBLIC_DEMO": "1"}):
        response = client.post("/api/verify", json={"code": "x=1", "mode": "static"})
    assert response.status_code == 200
    assert response.json()["status"] == "passed"


def test_public_preview_github_disabled_before_network_call():
    payload = {"token": "github_pat_TEST_TOKEN_123456", "repository": "demo", "filename": "main.py", "code": "print(1)"}
    with patch.dict(os.environ, {"AUTOPATCH_PUBLIC_DEMO": "1"}):
        with patch("app.main.github_publish", side_effect=AssertionError("must not publish")):
            response = client.post("/api/github/publish", json=payload)
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]


def test_public_preview_ai_disabled_before_external_call():
    with patch.dict(os.environ, {"AUTOPATCH_PUBLIC_DEMO": "1"}):
        with patch("app.llm.suggest_code", side_effect=AssertionError("must not call LLM")):
            response = client.post("/api/repair", json={"code": "print(1)", "use_ai": True})
    assert response.status_code == 200
    assert response.json()["ai_used"] is False
    assert "disabled" in response.json()["ai_message"]


def test_vscode_and_deployment_files_exist():
    for filename in ("Dockerfile", ".dockerignore", "compose.yaml", "render.yaml", "VSCODE_DEPLOY_GUIDE.md",
                     "SETUP_VSCODE.bat", "RUN_VSCODE.bat", "DEPLOY_PREVIEW.bat", ".vscode/tasks.json", ".vscode/launch.json"):
        assert (ROOT / filename).is_file(), filename
    assert "AUTOPATCH_PUBLIC_DEMO=1" in (ROOT / "Dockerfile").read_text()
    assert "/var/run/docker.sock" not in (ROOT / "compose.yaml").read_text()
