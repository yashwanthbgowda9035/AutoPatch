"""Sport Glass edition smoke tests: navigation effects remain visual-only."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_sport_glass_assets_served():
    home = client.get('/')
    assert home.status_code == 200
    assert 'sport-glass.css' in home.text
    assert 'sport-glass.js' in home.text
    assert 'id="sport-dock-preview"' in home.text
    assert 'VELOCITY 5.6' in home.text
    assert client.get('/assets/sport-glass.css').status_code == 200
    assert client.get('/assets/sport-glass.js').status_code == 200


def test_directional_zoom_and_reduced_motion_supported():
    css = client.get('/assets/sport-glass.css').text
    js = client.get('/assets/sport-glass.js').text
    assert '.scene.scene-exit' in css
    assert 'transform:scale(.67)' in css  # old rules are overridden by the optimized butter.css
    assert '@keyframes sportEnter' in css
    assert 'filter:blur(45px)' in css  # old rules are overridden by butter.css
    assert 'prefers-reduced-motion:reduce' in css
    assert 'pointer:coarse' in css
    assert 'pointerenter' in js
    assert 'pointerleave' in js
    assert 'focus' in js


def test_original_repair_api_still_available():
    response = client.post('/api/repair', json={
        'code': 'print(2*5', 'filename': 'untitled.txt', 'language': 'auto'
    })
    assert response.status_code == 200
    assert response.json()['repaired_code'] == 'print(2*5)'
