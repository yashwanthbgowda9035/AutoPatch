"""Cinema 5.0 full-screen scene navigation and preserved endpoint checks."""
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)


def test_fullscreen_scenes_and_no_orbit_menu():
    html=client.get('/').text
    assert 'id="scene-home"' in html
    assert 'id="scene-workspace"' in html
    assert 'id="scene-career"' in html
    assert 'id="scene-lab"' in html
    assert 'id="transition-shutter"' in html
    assert 'class="orbit-home"' not in html


def test_navigation_switches_scenes_without_page_scroll():
    js=client.get('/assets/cinema.js').text
    assert 'function switchScene(destination)' in js
    assert "nextScene.classList.add('active','scene-enter')" in js
    assert "previousScene.classList.add('scene-exit')" in js
    assert 'window.setTimeout' in js
    glass_css=client.get('/assets/glass-zoom.css').text
    assert '@keyframes glassSceneEnter' in glass_css
    assert 'backdrop-filter:blur(24px)' in glass_css
    assert 'window.scrollTo(' not in js
    css=client.get('/assets/cinema.css').text
    assert '#scene-root{position:relative;height:100vh' in css
    assert 'overflow-y:auto' in css
    assert '@media(prefers-reduced-motion:reduce)' in css


def test_repair_and_status_routes_still_respond():
    assert client.get('/api/status').status_code==200
    response=client.post('/api/repair',json={'code':'print(2*5','filename':'untitled.txt','language':'auto'})
    assert response.status_code==200
    assert response.json()['repaired_code']=='print(2*5)'
