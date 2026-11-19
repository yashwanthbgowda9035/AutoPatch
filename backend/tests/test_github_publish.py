from fastapi.testclient import TestClient
from app.main import app
from app import github_publish

client=TestClient(app)


def request(**changes):
    data={"token":"github_pat_TEST_TOKEN_123456", "repository":"demo-repo", "filename":"main.py", "code":"print('ok')", "create_new":True}
    data.update(changes)
    return data


def test_github_ui():
    html=client.get('/').text
    assert 'data-scene="github"' in html
    assert 'id="github-publish"' in html
    assert client.get('/assets/github.js').status_code==200
    assert client.get('/assets/github.css').status_code==200


def test_reject_path_traversal():
    res=client.post('/api/github/publish',json=request(filename='../secret.py'))
    assert res.status_code==422


def test_reject_blank_source():
    res=client.post('/api/github/publish',json=request(code=''))
    assert res.status_code==422


def test_new_repository_flow(monkeypatch):
    calls=[]
    def fake(method,path,token,data=None):
        calls.append((method,path,data))
        if path=='/user':return {'login':'developer'}
        if path=='/user/repos':return {'owner':{'login':'developer'}}
        if method=='PUT':return {'content':{'html_url':'https://github.com/developer/demo-repo/blob/main/main.py'},'commit':{'sha':'abc123'}}
        raise AssertionError((method,path))
    monkeypatch.setattr(github_publish,'github_call',fake)
    response=client.post('/api/github/publish',json=request())
    assert response.status_code==200
    assert response.json()['repository_url']=='https://github.com/developer/demo-repo'
    assert calls[-1][2]['content']=='cHJpbnQoJ29rJyk='


def test_existing_repository_updates_sha(monkeypatch):
    def fake(method,path,token,data=None):
        if path=='/user':return {'login':'developer'}
        if method=='GET':return {'type':'file','sha':'oldsha'}
        if method=='PUT':
            assert data['sha']=='oldsha'
            return {'content':{},'commit':{'sha':'newsha'}}
        raise AssertionError((method,path))
    monkeypatch.setattr(github_publish,'github_call',fake)
    response=client.post('/api/github/publish',json=request(create_new=False,owner='teammate'))
    assert response.status_code==200
    assert response.json()['repository_url']=='https://github.com/teammate/demo-repo'
