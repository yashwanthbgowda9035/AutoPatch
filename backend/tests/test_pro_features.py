"""Regression tests for multi-language diagnostics and Excel career matching."""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app import career, multilang

client = TestClient(app)
DEMO = Path(__file__).resolve().parents[2] / 'examples'


def test_cinema_dashboard_and_example_files_served():
    home = client.get('/').text
    assert 'scene-career' in home and 'language-select' not in home
    assert 'cinema.css' in home and 'id="stdout"' in home and 'id="stderr"' in home
    assert client.get('/assets/cinema.css').status_code == 200
    assert client.get('/assets/cinema.js').status_code == 200
    assert client.get('/examples/AutoPatch_Career_Jobs_DEMO.xlsx').status_code == 200


def test_languages_are_reported():
    data = client.get('/api/status').json()
    assert data['cv_excel_matching'] is True
    assert set(data['languages']) == {'python','c','cpp','java','excel'}


def test_c_unsafe_input_is_detected():
    response = client.post('/api/analyze',json={'filename':'main.c','language':'c','code':'char buf[10]; gets(buf);'})
    assert response.status_code == 200
    assert any(i['rule'] == 'ML-C-GETS' for i in response.json()['issues'])


def test_cpp_copy_is_detected():
    response = client.post('/api/analyze',json={'filename':'demo.cpp','language':'cpp','code':'char d[4]; strcpy(d, "long");'})
    assert any(i['rule'] == 'ML-CPP-STRCPY' for i in response.json()['issues'])


def test_java_case_patch_not_comment_or_string():
    source = 'class Main { void f(){ System.out.Println("ok"); /* System.out.Println("bad") */ } }'
    r = client.post('/api/repair',json={'filename':'Main.java','language':'java','code':source})
    data = r.json()
    assert data['changed'] is True
    assert 'System.out.println("ok")' in data['repaired_code']
    assert '/* System.out.Println("bad") */' in data['repaired_code']
    assert data['syntax_valid'] is None
    assert data['applied_fixes']


def test_java_literal_does_not_raise_false_positive():
    data = multilang.analyze('class T {String s = "System.out.Println()";}', 'java')
    assert data['total_issues'] == 0


def test_excel_formula_diagnostics():
    data = client.post('/api/analyze',json={'code':'=SUM(#REF!:A3)\n=A1/0\n=OFFSET(A1,1,0)', 'language':'excel', 'filename':'Sheet1.formula'}).json()
    rules = {x['rule'] for x in data['issues']}
    assert {'XL-REF-001','XL-DIV-001','XL-VOL-001'}.issubset(rules)


def test_non_python_verification_is_explicitly_unavailable():
    data = client.post('/api/verify',json={'code':'int main(){}','language':'c','mode':'docker'}).json()
    assert data['status'] == 'unavailable' and 'Python only' in data['message']


def test_demo_xlsx_has_fictional_jobs():
    jobs = career.read_jobs((DEMO / 'AutoPatch_Career_Jobs_DEMO.xlsx').read_bytes(),'demo.xlsx')
    assert len(jobs) == 5 and all('[DEMO]' in j['company'] for j in jobs)


def test_cv_excel_matching_end_to_end():
    cv = (DEMO / 'Demo_Resume.txt').read_bytes()
    jobs = (DEMO / 'AutoPatch_Career_Jobs_DEMO.xlsx').read_bytes()
    payload = {'cv_filename':'cv.txt','cv_base64':base64.b64encode(cv).decode(),
               'jobs_filename':'jobs.xlsx','jobs_base64':base64.b64encode(jobs).decode()}
    r = client.post('/api/career/match',json=payload)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result['jobs_checked'] == 5
    assert result['summary']['meets_listed_requirements'] >= 1
    assert result['profile']['degree'] == 'B.Tech'
    assert result['profile']['cgpa'] == 8.2
    assert result['profile']['graduation_year'] == 2027
    assert result['profile']['experience_years'] == 0
    assert 'Not official eligibility' in result['disclaimer']


def test_csv_job_import():
    data = b'Company,Job Title,Required Skills\nIllustrative Sample,Fellow,"Python, Excel"\n'
    jobs = career.read_jobs(data, 'jobs.csv')
    assert jobs[0]['company'] == 'Illustrative Sample'
    assert career.match_jobs(career.parse_resume('Python, Excel'), jobs)[0]['status'] == 'meets_listed_requirements'


def test_missing_resume_values_trigger_needs_review():
    profile = career.parse_resume('Skills: Java, Git')
    jobs = [{'company':'Example','job_title':'Java Trainee','required_skills':'Java','min_cgpa':'8.0','degree':'B.Tech'}]
    assert career.match_jobs(profile,jobs)[0]['status'] == 'needs_review'


def test_rejects_bad_file_types_and_paths():
    payload={'cv_filename':'virus.exe','cv_base64':base64.b64encode(b'a').decode(),
             'jobs_filename':'jobs.xlsx','jobs_base64':base64.b64encode(b'a').decode()}
    assert client.post('/api/career/match',json=payload).status_code == 422
    assert client.post('/api/analyze',json={'code':'pass', 'filename':'../../main.py'}).status_code == 422


def test_rejects_excessive_input():
    try:
        career.decode_file('A'*(career.MAX_FILE_BYTES * 4//3 + 200))
    except ValueError:
        pass
    else:
        raise AssertionError('Expected file size limit')


def test_c_printf_case_is_repaired_without_touching_comments():
    source = '// PRINTF("untouched")\nint main(){ PRINTF("hi"); }'
    r = client.post('/api/repair',json={'filename':'main.c','language':'c','code':source}).json()
    assert r['changed'] is True
    assert '// PRINTF("untouched")' in r['repaired_code']
    assert 'printf("hi")' in r['repaired_code']


def test_cpp_cout_case_is_repaired():
    source = 'int main(){ std::Cout << "hi"; }'
    r = client.post('/api/repair',json={'filename':'main.cpp','language':'cpp','code':source}).json()
    assert r['changed'] is True
    assert 'std::cout' in r['repaired_code']
