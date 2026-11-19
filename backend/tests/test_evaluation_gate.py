"""Quality and security regression checks for the GitHub evaluation package."""
from __future__ import annotations

import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app
from app.engine import analyze

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def test_security_headers_on_dashboard_and_api():
    for path in ('/', '/api/samples', '/assets/cinema.js'):
        res = client.get(path)
        assert res.status_code == 200
        assert res.headers['x-content-type-options'] == 'nosniff'
        assert res.headers['x-frame-options'] == 'DENY'
        assert "script-src 'self'" in res.headers['content-security-policy']
    assert client.get('/api/samples').headers['cache-control'] == 'no-store'


def test_untrusted_host_rejected():
    res = client.get('/', headers={'host': 'malicious.example'})
    assert res.status_code == 400


def test_docs_and_version_consistent():
    assert client.get('/health').json()['version'] == '5.6.0'
    assert 'VELOCITY 5.6' in client.get('/').text
    assert (ROOT / 'RUN_QUALITY_GATE.bat').exists()
    assert (ROOT / 'EVALUATION.md').exists()
    assert (ROOT / '.github/workflows/tests.yml').exists()


def test_long_source_static_analysis_is_bounded():
    # Exercises a formerly quadratic AST-walk implementation. Use a generous
    # threshold to avoid flaky CI on slower Windows runners.
    code = 'numbers = list(range(10))\n' + '\n'.join(
        f'val{i} = sum(numbers) / len(numbers)' for i in range(450)
    )
    result = analyze(code)
    assert result['syntax_valid']
    assert result['total_issues'] == 0
    assert result['duration_ms'] < 4000


def test_evaluation_css_and_runtime_ui_present():
    html = client.get('/').text
    assert '/assets/evaluation.css' in html
    assert 'aria-label="Source code editor"' in html
    assert client.get('/assets/evaluation.css').status_code == 200
    assert client.get('/examples/Student_NameError_BUGGY.py').status_code == 200
