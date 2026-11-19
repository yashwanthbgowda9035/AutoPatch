"""Obsidian automatic language detection and opt-in Docker stdout/stderr tests."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app import autodetect, runner
from app.samples import SAMPLES

client = TestClient(app)


def test_all_samples_detected_correctly():
    for sample in SAMPLES:
        expected = sample.get('language', 'python')
        result = autodetect.detect(sample['code'], sample.get('filename','untitled'))
        assert result['language'] == expected, sample['id']


def test_pasted_language_detects_from_content_not_default_filename():
    source = 'public class Main { public static void main(String[] args) { System.out.Println("hi"); } }'
    r = client.post('/api/analyze',json={'code': source, 'filename':'main.py', 'language':'auto'})
    assert r.status_code == 200
    data = r.json()
    assert data['detected_language'] == 'java'
    assert data['total_issues'] >= 1
    assert data['detection']['reason']


def test_pasted_excel_formula_detection():
    result = client.post('/api/analyze',json={'code':'=A1/0\n=SUM(#REF!:B3)', 'language':'auto'}).json()
    assert result['detected_language'] == 'excel'
    assert result['total_issues'] >= 2


def test_detect_endpoint_explains_tentative_cases():
    result = client.post('/api/detect',json={'code':'x = 2'}).json()
    assert result['language'] in autodetect.LANGUAGES
    assert result['tentative'] is True
    assert result['confidence'] < .66


def test_auto_repair_java_case():
    result = client.post('/api/repair',json={'code':'public class Main { void f() { System.out.Println("hi"); } }'}).json()
    assert result['detected_language'] == 'java'
    assert result['changed']
    assert 'System.out.println(' in result['repaired_code']


def test_python_syntax_error_displays_real_error_without_exec():
    response = client.post('/api/run',json={'code':'def broken(:\n  pass\n'}).json()
    assert response['detected_language'] == 'python'
    assert response['status'] == 'failed'
    assert response['phase'] == 'syntax'
    assert 'syntax' in response['message'].lower()
    assert not response['executed']


def test_no_docker_never_executes_code():
    with patch.object(runner.shutil,'which', return_value=None):
        response = client.post('/api/run',json={'code':'print(42)'}).json()
    assert response['status'] == 'unavailable'
    assert response['executed'] is False
    assert response['exit_code'] is None
    assert 'Docker' in response['message']


def test_excel_formula_never_executes():
    data = client.post('/api/run',json={'code':'=SUM(A1:A4)'}).json()
    assert data['detected_language'] == 'excel'
    assert data['status'] == 'unavailable'
    assert data['executed'] is False


def test_python_docker_real_streams_are_separate_mocked():
    calls=[]
    class Fake:
        def __init__(self,code,stdout='',stderr=''):
            self.returncode=code;self.stdout=stdout;self.stderr=stderr
    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[:2]==['docker','info']:return Fake(0,'29.0')
        if argv[:3]==['docker','image','inspect']:return Fake(0,'available')
        assert argv[:2] == ['docker','run']
        return Fake(1,stdout='partial stdout\n', stderr='Traceback in main.py\n')
    with patch.object(runner.shutil,'which', return_value='/usr/bin/docker'), patch.object(runner.subprocess,'run', side_effect=fake_run):
        data = client.post('/api/run',json={'code':'print("hi")\nraise ValueError("failed")\n'}).json()
    assert data['status'] == 'failed'
    assert data['executed'] is True
    assert data['stdout'] == 'partial stdout\n'
    assert 'Traceback' in data['stderr']
    cmd=calls[-1]
    assert '--network' in cmd and cmd[cmd.index('--network')+1]=='none'
    assert '--read-only' in cmd and '--cap-drop' in cmd and '--memory' in cmd


def test_missing_c_compiler_image_guides_setup():
    class Fake:
        def __init__(self,code): self.returncode=code;self.stdout='';self.stderr=''
    with patch.object(runner.shutil,'which', return_value='/bin/docker'), patch.object(runner.subprocess,'run',side_effect=[Fake(0),Fake(1)]):
        response = client.post('/api/run',json={'code':'#include <stdio.h>\nint main(void){puts("ok");return 0;}'}).json()
    assert response['status'] == 'unavailable'
    assert 'docker pull gcc:14' in response['message']


def _test_xlsx_bytes():
    import io, zipfile
    contents = '''<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>SUM(B1:B4)</f><v>50</v></c><c r="C1" t="e"><f>A1/0</f><v>#DIV/0!</v></c></row><row r="2"><c r="D2"><f>SUM(#REF!:A2)</f></c></row></sheetData></worksheet>'''
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('xl/worksheets/sheet1.xml', contents)
    return out.getvalue()


def test_xlsx_audit_reports_cell_formula_and_saved_values():
    import base64
    payload={'filename':'example.xlsx','data_base64':base64.b64encode(_test_xlsx_bytes()).decode()}
    result=client.post('/api/workbook/analyze',json=payload)
    assert result.status_code==200, result.text
    data=result.json()
    assert data['detected_language']=='excel'
    assert data['total_formulas']==3
    assert data['cached_value_count']==2
    assert data['rows'][0]['cached_value']=='50'
    assert any(i['cell']=='C1' and i['rule']=='XL-DIV-001' for i in data['issues'])
    assert any(i['rule']=='XL-CACHE-ERR' for i in data['issues'])
    assert 'NOT recalculated' in data['note']


def test_invalid_xlsx_is_rejected():
    import base64
    payload={'filename':'fake.xlsx','data_base64':base64.b64encode(b'not an xlsx').decode()}
    assert client.post('/api/workbook/analyze',json=payload).status_code==422


def test_cinema_assets_and_sample_workbook_are_served():
    home = client.get('/').text
    assert 'AutoPatch // VELOCITY' in home
    assert 'id="language-select"' not in home
    assert 'id="stdout"' in home and 'id="stderr"' in home
    assert 'AutoPatch_Formula_Audit_DEMO.xlsx' in home
    for path in ['/assets/cinema.css','/assets/cinema.js','/examples/AutoPatch_Formula_Audit_DEMO.xlsx']:
        assert client.get(path).status_code == 200, path


def test_cpp_and_java_runtime_output_path_mocked():
    class Fake:
        def __init__(self,code,stdout='',stderr=''):
            self.returncode=code;self.stdout=stdout;self.stderr=stderr
    for language,code,expected in [
        ('cpp','#include <iostream>\nint main(){std::cout << "Hi";}','g++'),
        ('java','public class Main {public static void main(String[] a){System.out.println("Hi");}}','javac'),
    ]:
        calls=[]
        def fake_run(argv, **kwargs):
            calls.append(argv)
            if argv[:2]==['docker','info']:return Fake(0)
            if argv[:3]==['docker','image','inspect']:return Fake(0)
            return Fake(0,stdout='Hi')
        with patch.object(runner.shutil,'which',return_value='/usr/bin/docker'), patch.object(runner.subprocess,'run',side_effect=fake_run):
            r=client.post('/api/run',json={'code':code,'language':'auto'}).json()
        assert r['detected_language']==language
        assert r['status']=='passed' and r['stdout']=='Hi' and r['stderr']==''
        assert expected in ' '.join(calls[-1])
