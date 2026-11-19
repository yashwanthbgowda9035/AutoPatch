"""Regression tests for the previously missed 'student' / 'students' NameError.

All execution outputs are mocked: no untrusted code runs on the test host.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.engine import analyze, repair, runtime_issues
from app.main import app

client = TestClient(app)

SOURCE = '''students = [80, 90, 70]
total = sum(students)
average = total / len(student)
print(average)
'''
TRACE = '''Traceback (most recent call last):
  File "/workspace/main.py", line 3, in <module>
    average = total / len(student)
                          ^^^^^^^
NameError: name 'student' is not defined. Did you mean: 'students'?
'''


def test_static_typo_is_detected_without_docker():
    result = analyze(SOURCE)
    assert result['syntax_valid']
    assert result['total_issues'] == 1
    assert result['issues'][0]['rule'] == 'PY-NAME-002'
    assert result['issues'][0]['fix_available']


def test_typo_repair_is_minimal_and_parseable():
    result = repair(SOURCE)
    assert result['changed']
    assert result['repaired_code'] == SOURCE.replace('len(student)', 'len(students)')
    assert result['syntax_valid']
    ast.parse(result['repaired_code'])


def test_runtime_traceback_is_actionable():
    issues = runtime_issues(SOURCE, TRACE, 1)
    assert len(issues) == 1
    assert issues[0]['rule'] == 'PY-RUNTIME-401'
    assert issues[0]['line'] == 3
    assert issues[0]['fix_available']
    result = repair(SOURCE, TRACE, 1)
    assert result['changed']
    assert len(result['applied_fixes']) == 1
    assert result['applied_fixes'][0]['rule'] == 'PY-RUNTIME-401'
    assert 'runtime' in result['repair_mode']


def test_runtime_endpoint_surfaces_error_and_repair():
    mock = {'status': 'failed', 'stderr': TRACE, 'stdout': '', 'exit_code': 1, 'message': 'Program failed', 'phase': 'compile_or_run'}
    with patch('app.main.runner.run_code', return_value=mock):
        response = client.post('/api/run', json={'code': SOURCE, 'filename': 'demo.py'})
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert body['runtime_issues'][0]['rule'] == 'PY-RUNTIME-401'
    fixed = client.post('/api/repair', json={'code': SOURCE, 'runtime_stderr': body['stderr'], 'runtime_exit_code': body['exit_code']})
    assert fixed.status_code == 200
    assert fixed.json()['repaired_code'].splitlines()[2] == 'average = total / len(students)'


def test_name_error_inside_function_uses_runtime_not_static():
    source = 'def score(students):\n    return sum(students) / len(student)\n\nprint(score([2, 4]))\n'
    trace = '''Traceback (most recent call last):
  File "/workspace/main.py", line 4, in <module>
    print(score([2, 4]))
  File "/workspace/main.py", line 2, in score
    return sum(students) / len(student)
NameError: name 'student' is not defined. Did you mean: 'students'?
'''
    assert not any(i['rule'] == 'PY-NAME-002' for i in analyze(source)['issues'])
    fixed = repair(source, trace, 1)
    assert fixed['changed']
    assert 'len(students)' in fixed['repaired_code']


def test_no_repair_for_missing_candidate():
    source = 'total = 1\nprint(student)\n'
    issues = runtime_issues(source, TRACE.replace('line 3', 'line 2'), 1)
    assert issues and not issues[0]['fix_available']
    assert not repair(source)['changed']


def test_no_repair_for_ambiguous_candidates():
    source = 'students = [1]\nstudentx = [2]\nprint(student)\n'
    assert not repair(source)['changed']


def test_no_repair_for_wrong_hint():
    trace = TRACE.replace("'students'?", "'studentx'?")
    issues = runtime_issues(SOURCE, trace, 1)
    assert issues and not issues[0]['fix_available']


def test_no_repair_for_successful_run_even_with_stderr_text():
    assert runtime_issues(SOURCE, TRACE, 0) == []
    assert runtime_issues(SOURCE, TRACE, None) == []


def test_no_repair_for_traceback_from_different_file():
    trace = TRACE.replace('/workspace/main.py', '/tmp/attacker.py')
    issues = runtime_issues(SOURCE, trace, 1)
    assert issues and not issues[0]['fix_available']


def test_no_repair_for_exception_text_spoof():
    source = 'raise NameError("name \'student\' is not defined. Did you mean: \'students\'?")\n'
    trace = 'Traceback (most recent call last):\n  File "/workspace/main.py", line 1, in <module>\nNameError: name \'student\' is not defined. Did you mean: \'students\'?\n'
    assert not runtime_issues(source, trace, 1)[0]['fix_available']


def test_do_not_modify_comments_or_strings():
    source = 'students = [1]\nmessage = "student"\n# student\nprint(len(student))\n'
    fixed = repair(source)
    assert 'message = "student"' in fixed['repaired_code']
    assert '# student' in fixed['repaired_code']
    assert 'len(students)' in fixed['repaired_code']


def test_no_guess_when_wildcard_import_may_supply_name():
    source = 'from mystery import *\nstudents = [1]\nprint(student)\n'
    assert not repair(source)['changed']


def test_no_guess_for_dynamic_exec():
    source = 'students = [1]\nexec("student = 1")\nprint(student)\n'
    assert not repair(source)['changed']


def test_utf8_offset_repair():
    source = 'students = [1]\nmessage = "🚀"; print(len(student))\n'
    assert 'print(len(students))' in repair(source)['repaired_code']


def test_reject_overlong_runtime_traceback():
    response = client.post('/api/repair', json={'code': SOURCE, 'runtime_stderr': 'x' * 12001, 'runtime_exit_code': 1})
    assert response.status_code == 422


def test_runtime_other_exception_is_not_clean():
    source = 'x = 1 / 0\n'
    trace = 'Traceback (most recent call last):\n  File "/workspace/main.py", line 1, in <module>\nZeroDivisionError: division by zero\n'
    issues = runtime_issues(source, trace, 1)
    assert issues and issues[0]['rule'] == 'PY-RUNTIME-499'
    assert not issues[0]['fix_available']


def test_runtime_code_not_executed_during_analysis():
    source = 'students = [1]\nraise RuntimeError("must not execute")\nprint(student)\n'
    assert analyze(source)['syntax_valid']
    assert repair(source)['syntax_valid']


def test_docker_unavailable_not_misreported_as_runtime_error():
    with patch('app.main.runner.run_code', return_value={'status':'unavailable','message':'Docker missing','stderr':'','exit_code':None}):
        response = client.post('/api/run', json={'code': SOURCE})
    assert response.json()['runtime_issues'] == []


def test_frontend_has_runtime_to_repair_bridge():
    root = Path(__file__).resolve().parents[2]
    js = (root / 'frontend/assets/cinema.js').read_text()
    assert 'run.runtime_issues' in js
    assert 'runtime_stderr' in js
    assert 'showRepair(suggestion)' in js
    assert "state.repair.original_code!==$('code-editor').value" in js


def test_custom_uppercase_print_function_is_preserved():
    source = 'def PRINT(message):\n    return message.upper()\nprint(PRINT("hello"))\n'
    assert not repair(source)['changed']


def test_custom_print_alias_is_preserved():
    source = 'PRINT = lambda message: message\nprint(PRINT("hello"))\n'
    assert not repair(source)['changed']


def test_partial_syntax_fix_not_misrepresented_as_valid_patch():
    source = 'def demo()\n    print("ok")\n    return (1 +\n'
    result = repair(source)
    assert not result['syntax_valid']
    assert not result['changed']
    assert not result['applied_fixes']


def test_comprehension_binding_is_not_mistaken_for_name_typo():
    source = 'students = [1, 2]\nprint([student for student in students])\n'
    assert not repair(source)['changed']


def test_lambda_parameter_is_not_mistaken_for_name_typo():
    source = 'students = [1]\nfn = lambda student: student\nprint(fn(2))\n'
    assert not repair(source)['changed']
