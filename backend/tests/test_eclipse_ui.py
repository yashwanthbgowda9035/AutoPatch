"""UI regression checks for the Eclipse code-first redesign."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app, FRONTEND

client=TestClient(app)


def test_cinema_editor_has_no_preloaded_programs_or_popups():
    html = client.get('/').text
    assert 'id="code-editor"' in html and 'id="system-messages"' in html
    assert 'id="sample-select"' not in html and 'id="toast"' not in html
    assert 'id="code-output-panel"' not in html
    js = client.get('/assets/cinema.js').text
    assert "$('code-editor').value" in js and 'window.alert(' not in js
    assert '/api/samples' not in js


def test_diagnostics_and_stdout_stderr_are_side_by_side():
    html = client.get('/').text
    assert 'class="workspace-layout"' in html
    assert 'class="results-column"' in html
    assert 'id="diagnostics"' in html
    assert 'id="stdout"' in html and 'id="stderr"' in html
    css = client.get('/assets/cinema.css').text
    assert 'grid-template-columns:minmax(0,1.3fr) minmax(310px,1fr)' in css
    assert 'prefers-reduced-motion' in css


def test_no_safe_fix_preserves_source_and_returns_review_state():
    code='def compute_ratio(total):\n    return total / 0\n'
    analysis=client.post('/api/analyze',json={'code':code,'filename':'untitled.txt','language':'auto'})
    assert analysis.status_code==200
    assert analysis.json()['total_issues']>=1
    repair=client.post('/api/repair',json={'code':code,'filename':'untitled.txt','language':'auto'})
    assert repair.status_code==200
    assert repair.json()['changed'] is False
    assert repair.json()['repaired_code']==code


def test_python_missing_parenthesis_is_detected_and_repaired_without_presets():
    code='print(2*5'
    body={'code':code,'filename':'untitled.txt','language':'auto'}
    a=client.post('/api/analyze',json=body).json()
    assert a['detected_language']=='python' and a['total_issues']>=1
    r=client.post('/api/repair',json=body).json()
    assert r['changed'] is True
    assert r['repaired_code']=='print(2*5)'


def test_cinema_assets_are_served():
    html = client.get('/').text
    assert 'AutoPatch // VELOCITY' in html
    for asset in ('cinema.css','cinema.js','cinema-landscape.svg'):
        response=client.get('/assets/'+asset)
        assert response.status_code==200 and len(response.content)>50
