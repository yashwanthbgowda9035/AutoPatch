"""The motion UI serves its own static assets and preserves core routes."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, FRONTEND

client = TestClient(app)


def test_cinematic_scene_is_default():
    response = client.get('/')
    assert response.status_code == 200
    assert 'id="scene-home" class="scene scene-home active"' in response.text
    assert 'data-scene="workspace"' in response.text
    assert 'data-scene="career"' in response.text


def test_cinema_assets_serve_without_cdn():
    for name in ('cinema.css','cinema.js','cinema-landscape.svg'):
        response = client.get('/assets/'+name)
        assert response.status_code == 200
        assert len(response.content) > 1000
    document = (FRONTEND/'index.html').read_text(encoding='utf-8')
    assert 'https://cdn.' not in document


def test_frontend_uses_real_endpoints():
    source = (FRONTEND/'assets'/'cinema.js').read_text(encoding='utf-8')
    for endpoint in ('/api/analyze', '/api/repair','/api/run','/api/verify','/api/workbook/analyze','/api/career/match'):
        assert endpoint in source
    assert '/api/samples' not in source
    assert 'data-scene' in (FRONTEND/'index.html').read_text(encoding='utf-8')
