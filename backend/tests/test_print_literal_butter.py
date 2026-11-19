"""Simple print syntax repair remains conservative and never executes user input."""
import ast
from fastapi.testclient import TestClient
from app.engine import analyze, repair
from app.main import app

client = TestClient(app)


def test_print_hello_missing_quote_and_parentheses():
    source = 'print"hello'
    report = analyze(source)
    assert report['syntax_valid'] is False
    assert report['fixable_issues'] == 1
    assert report['issues'][0]['rule'] == 'PY-SYNTAX-004'
    proposed = repair(source)
    assert proposed['changed'] and proposed['syntax_valid']
    assert proposed['repaired_code'] == 'print("hello")'
    ast.parse(proposed['repaired_code'])


def test_print_hello_valid_quotes_missing_call_parentheses():
    for source in ['print"hello"', "print 'hello'", 'print "hello"\n']:
        result = repair(source)
        assert result['changed'] and result['syntax_valid']
        assert 'print(' in result['repaired_code']


def test_comments_and_indented_print_strings():
    source = 'if True:\n    print"hello\n'
    assert repair(source)['repaired_code'] == 'if True:\n    print("hello")\n'
    assert repair('# comment\nprint"hello\n')['repaired_code'] == '# comment\nprint("hello")\n'


def test_no_unsafe_guess_for_ambiguous_strings():
    for source in ['print("hello)', 'print"hello\\n', 'print"hello"+suffix', 'print"a;command', 'print"value" # explanation', 'f=print"hello', 'print"hello";danger()']:
        assert repair(source)['changed'] is False, source


def test_api_repair_print_literal_and_original_unchanged():
    response = client.post('/api/repair', json={'code':'print"hello', 'filename':'untitled', 'language':'auto'})
    assert response.status_code == 200
    data = response.json()
    assert data['original_code'] == 'print"hello'
    assert data['repaired_code'] == 'print("hello")'
    assert data['changed'] is True


def test_butter_assets_work_without_changing_functional_controls():
    home = client.get('/')
    assert home.status_code == 200
    assert 'butter.css' in home.text
    css = client.get('/assets/butter.css')
    assert css.status_code == 200
    assert 'butterSceneIn' in css.text
    assert 'prefers-reduced-motion:reduce' in css.text
