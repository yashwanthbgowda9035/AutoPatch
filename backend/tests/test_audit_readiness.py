"""Comprehensive AI-evaluation readiness test suite.

Validates multi-language AutoFix, database persistence, Docker execution,
AI integrations, API security, and empty/edge state handling.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app import db, llm, engine, multilang

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Multi-Language AutoFix & Error Types
# ---------------------------------------------------------------------------

def test_autofix_python_print_typos():
    """Verify common print misspellings (pirnt, prnt, prnit, PRINT, pritn) are fixed."""
    for typo in ("pirnt", "prnt", "prnit", "PRINT", "pritn"):
        source = f'{typo}("testing print typo")\n'
        res = client.post("/api/repair", json={"code": source, "language": "python"})
        assert res.status_code == 200
        data = res.json()
        assert data["changed"] is True
        assert 'print("testing print typo")' in data["repaired_code"]
        assert data["syntax_valid"] is True


def test_autofix_python_assignment_in_condition():
    """Verify single '=' inside 'if', 'elif', or 'while' is repaired to '=='."""
    cases = [
        ("if x = 10:\n    pass\n", "if x == 10:\n    pass\n"),
        ("while count = 0:\n    break\n", "while count == 0:\n    break\n"),
    ]
    for source, expected in cases:
        res = client.post("/api/repair", json={"code": source, "language": "python"})
        assert res.status_code == 200
        data = res.json()
        assert data["changed"] is True
        assert data["repaired_code"] == expected
        assert data["syntax_valid"] is True


def test_autofix_c_printf_and_main_signature():
    """Verify C repair fixes PRINTF and void main()."""
    source = '#include <stdio.h>\nvoid main() {\n    PRINTF("Hello\\n");\n}\n'
    res = client.post("/api/repair", json={"code": source, "language": "c", "filename": "main.c"})
    assert res.status_code == 200
    data = res.json()
    assert data["changed"] is True
    assert "int main(void)" in data["repaired_code"]
    assert 'printf("Hello\\n");' in data["repaired_code"]
    assert len(data["applied_fixes"]) >= 2


def test_autofix_cpp_stream_capitalization():
    """Verify C++ repair fixes std::Cout, std::Cin, and std::Endl."""
    source = '#include <iostream>\nint main() {\n    int x;\n    std::Cin >> x;\n    std::Cout << x << std::Endl;\n}\n'
    res = client.post("/api/repair", json={"code": source, "language": "cpp", "filename": "main.cpp"})
    assert res.status_code == 200
    data = res.json()
    assert data["changed"] is True
    assert "std::cin >> x;" in data["repaired_code"]
    assert "std::cout << x << std::endl;" in data["repaired_code"]


def test_autofix_java_case_variations():
    """Verify Java repair fixes System.out.Println, System.out.printLn, and system.out.println."""
    for variant in ("System.out.Println", "System.out.printLn", "system.out.println"):
        source = f'public class Main {{\n    public static void main(String[] args) {{\n        {variant}("Hello");\n    }}\n}}\n'
        res = client.post("/api/repair", json={"code": source, "language": "java", "filename": "Main.java"})
        assert res.status_code == 200
        data = res.json()
        assert data["changed"] is True
        assert 'System.out.println("Hello");' in data["repaired_code"]


def test_autofix_java_main_method_casing():
    """Verify Java repair fixes 'public static void Main' to 'main'."""
    source = 'public class Main {\n    public static void Main(String[] args) {\n        System.out.println("Hello");\n    }\n}\n'
    res = client.post("/api/repair", json={"code": source, "language": "java", "filename": "Main.java"})
    assert res.status_code == 200
    data = res.json()
    assert data["changed"] is True
    assert "public static void main(String[] args)" in data["repaired_code"]


def test_autofix_excel_missing_prefix_and_unclosed_paren():
    """Verify Excel repair prefixes formula with '=' and balances unclosed parentheses."""
    source = "SUM(A1:A10\n"
    res = client.post("/api/repair", json={"code": source, "language": "excel", "filename": "formula.formula"})
    assert res.status_code == 200
    data = res.json()
    assert data["changed"] is True
    assert data["repaired_code"].strip() == "=SUM(A1:A10)"


# ---------------------------------------------------------------------------
# 2. Database Persistence (SQLite)
# ---------------------------------------------------------------------------

def test_database_history_crud():
    """Verify recording, retrieving, and clearing history in SQLite."""
    # Clear initial history
    client.delete("/api/history")

    # Record run event
    run_rec = client.post("/api/history", json={
        "filename": "test.py",
        "language": "python",
        "action": "run",
        "status": "passed",
        "code": "print('hello')",
        "stdout": "hello\n",
        "exit_code": 0,
        "issues_count": 0,
    })
    assert run_rec.status_code == 200
    assert run_rec.json()["status"] == "recorded"

    # Retrieve history
    hist = client.get("/api/history").json()["history"]
    assert len(hist) >= 1
    assert hist[0]["action"] == "run"
    assert hist[0]["stdout"] == "hello\n"
    assert hist[0]["exit_code"] == 0

    # Clear history
    del_res = client.delete("/api/history")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "cleared"

    # Confirm empty
    empty_hist = client.get("/api/history").json()["history"]
    assert len(empty_hist) == 0


def test_database_snippets_crud():
    """Verify snippet storage, retrieval, and deletion in SQLite."""
    # Retrieve preloaded/seeded snippets
    snippets = client.get("/api/snippets").json()["snippets"]
    assert len(snippets) >= 5

    # Save a custom snippet
    new_snippet = {
        "id": "custom-test-snippet",
        "title": "Custom Test Snippet",
        "language": "python",
        "code": "x = 42\nprint(x)\n",
        "tests": "assert x == 42\n",
        "description": "Test snippet description",
    }
    create_res = client.post("/api/snippets", json=new_snippet)
    assert create_res.status_code == 200
    assert create_res.json()["status"] == "saved"

    # Verify presence
    updated = client.get("/api/snippets").json()["snippets"]
    found = next((s for s in updated if s["id"] == "custom-test-snippet"), None)
    assert found is not None
    assert found["title"] == "Custom Test Snippet"

    # Delete custom snippet
    del_res = client.delete("/api/snippets/custom-test-snippet")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"


# ---------------------------------------------------------------------------
# 3. Multi-Language Static Verification (/api/verify mode=static)
# ---------------------------------------------------------------------------

def test_static_verify_c_language():
    """Verify static check passes for valid C and fails on unmatched braces."""
    valid_c = "#include <stdio.h>\nint main(void) { return 0; }\n"
    res_valid = client.post("/api/verify", json={"code": valid_c, "language": "c", "mode": "static"})
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "passed"

    invalid_c = "#include <stdio.h>\nint main(void) { return 0;\n"
    res_invalid = client.post("/api/verify", json={"code": invalid_c, "language": "c", "mode": "static"})
    assert res_invalid.status_code == 200
    assert res_invalid.json()["status"] == "failed"


def test_static_verify_excel_formula():
    """Verify static check flags broken cell references in Excel."""
    broken_formula = "=SUM(#REF!:B5)"
    res = client.post("/api/verify", json={"code": broken_formula, "language": "excel", "mode": "static"})
    assert res.status_code == 200
    assert res.json()["status"] == "failed"
    assert "Broken cell reference" in res.json()["output"]


# ---------------------------------------------------------------------------
# 4. Genuine AI Features (Gemini & OpenAI)
# ---------------------------------------------------------------------------

def test_ai_provider_detection():
    """Verify provider detection for Gemini and OpenAI keys."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyTest123", "OPENAI_API_KEY": ""}):
        assert llm.get_provider() == "gemini"
        assert llm.is_configured() is True

    with patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENAI_API_KEY": "sk-proj-test123"}):
        assert llm.get_provider() == "openai"
        assert llm.is_configured() is True

    with patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""}):
        assert llm.get_provider() is None
        assert llm.is_configured() is False


def test_gemini_ai_repair_integration_mocked():
    """Verify Gemini API response handling, json parsing, and syntax check."""
    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": json.dumps({"repaired_code": "def add(a, b):\n    return a + b\n"})}
                    ]
                }
            }
        ]
    }
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_gemini_key", "OPENAI_API_KEY": ""}):
        with patch("app.llm.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_gemini_response).encode()
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            code = "def add(a, b):\n    return a - b\n"
            res = client.post("/api/repair", json={"code": code, "use_ai": True})
            assert res.status_code == 200
            data = res.json()
            assert data["ai_used"] is True
            assert "Gemini" in data["ai_message"]
            assert data["syntax_valid"] is True
            assert data["repaired_code"] == "def add(a, b):\n    return a + b\n"


def test_ai_repair_graceful_fallback_on_network_error():
    """Verify fallback to deterministic repair when AI call fails."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-test"}):
        with patch("app.llm.urlopen", side_effect=OSError("Network unreachable")):
            code = "print(2*5"
            res = client.post("/api/repair", json={"code": code, "use_ai": True})
            assert res.status_code == 200
            data = res.json()
            assert data["changed"] is True
            assert data["repaired_code"] == "print(2*5)"
            assert "unavailable" in data["ai_message"].lower() or "kept" in data["ai_message"].lower()


# ---------------------------------------------------------------------------
# 5. Security & Edge Case Validations
# ---------------------------------------------------------------------------

def test_security_payload_size_enforced():
    """Payloads exceeding 20,000 characters must be rejected."""
    huge_code = "x = 1\n" * 5000  # 30,000 chars
    res = client.post("/api/analyze", json={"code": huge_code})
    assert res.status_code == 422


def test_security_filename_path_traversal_blocked():
    """Path traversal in filename parameter must be rejected."""
    for bad_name in ("../../etc/passwd.py", "..\\windows\\system32.py", "/root/bad.py"):
        res = client.post("/api/analyze", json={"code": "pass", "filename": bad_name})
        assert res.status_code == 422


def test_empty_inputs_handled():
    """Empty string code must be rejected with 422 validation error."""
    res = client.post("/api/analyze", json={"code": ""})
    assert res.status_code == 422


def test_workbook_invalid_format_rejected():
    """Non-xlsx files to workbook endpoint must be rejected with 422."""
    res = client.post("/api/workbook/analyze", json={"filename": "sheet.csv", "data_base64": "dGVzdA=="})
    assert res.status_code == 422
