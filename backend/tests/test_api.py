"""HTTP endpoints, validation, and no-Docker regression tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.samples import SAMPLES

client = TestClient(app)


def test_home_serves_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "AutoPatch" in response.text
    assert "code-editor" in response.text


def test_styles_and_js_are_served():
    assert client.get("/assets/cinema.css").status_code == 200
    assert client.get("/assets/cinema.js").status_code == 200
    assert client.get("/assets/favicon.svg").status_code == 200


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_samples_endpoint():
    response = client.get("/api/samples")
    assert response.status_code == 200
    assert len(response.json()["samples"]) >= 5


def test_analyze_and_repair_api():
    snippet = SAMPLES[0]["code"]
    analysis = client.post("/api/analyze", json={"code": snippet})
    assert analysis.status_code == 200
    assert analysis.json()["fixable_issues"] == 1
    patched = client.post("/api/repair", json={"code": snippet})
    assert patched.status_code == 200
    assert patched.json()["syntax_valid"]
    assert patched.json()["changed"]
    assert not patched.json()["ai_used"]


def test_static_verify_does_not_run_code():
    response = client.post("/api/verify", json={"code": 'raise RuntimeError("must not run")\n', "mode": "static"})
    assert response.status_code == 200
    assert response.json()["status"] == "passed"
    assert "No code was executed" in response.json()["output"]


def test_invalid_syntax_reports_failed_not_503():
    response = client.post("/api/verify", json={"code": "def broken(:", "mode": "static"})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


def test_absent_docker_reports_unavailable_not_503():
    with patch("app.sandbox.docker_status", return_value={"available": False, "message": "Docker executable not found"}):
        response = client.post("/api/verify", json={"code": "x=1", "tests": "import unittest\n", "mode": "docker"})
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


def test_no_tests_status():
    response = client.post("/api/verify", json={"code": "x=1", "tests": "", "mode": "docker"})
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


def test_bad_filename_rejected():
    response = client.post("/api/analyze", json={"code": "pass", "filename": "../../hack.py"})
    assert response.status_code == 422


def test_code_size_rejected():
    response = client.post("/api/analyze", json={"code": "a" * 20001})
    assert response.status_code == 422


def test_ai_is_optional_without_config():
    with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
        response = client.post("/api/repair", json={"code": SAMPLES[0]["code"], "use_ai": True})
    assert response.status_code == 200
    assert not response.json()["ai_used"]
    assert "not set" in response.json()["ai_message"]


def test_filenames_with_spaces_accepted():
    response = client.post("/api/analyze", json={"code": "pass", "filename": "my script.py"})
    assert response.status_code == 200


def test_missing_delimiter_repair_public_api():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    payload = {"code": "print(2*5", "language": "auto"}
    diagnosis = client.post("/api/analyze", json=payload)
    assert diagnosis.status_code == 200
    analysis = diagnosis.json()
    assert analysis["detected_language"] == "python"
    assert any(item["rule"] == "PY-SYNTAX-003" and item["fix_available"] for item in analysis["issues"])
    fixed = client.post("/api/repair", json=payload)
    assert fixed.status_code == 200
    response = fixed.json()
    assert response["changed"] and response["syntax_valid"]
    assert response["repaired_code"] == "print(2*5)"
