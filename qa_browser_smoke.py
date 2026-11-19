"""Offline Chromium smoke test; no Docker or public network required.

Uses the real frontend HTML/CSS/JS, real FastAPI analyze/repair/verify
responses, and a simulated failed Docker traceback. Requires Playwright and
Chromium. This is a developer-only optional quality check, not a production test.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend'))
from app.main import app
client=TestClient(app)
SOURCE='students = [80, 90, 70]\ntotal = sum(students)\naverage = total / len(student)\nprint(average)\n'
TRACE='''Traceback (most recent call last):
  File "/workspace/main.py", line 3, in <module>
    average = total / len(student)
NameError: name 'student' is not defined. Did you mean: 'students'?
'''


def offline_html():
    html=(ROOT/'frontend/index.html').read_text()
    def css(match):
        data=(ROOT/'frontend'/match.group(1).lstrip('/')).read_text()
        data='\n'.join(line for line in data.splitlines() if not line.lstrip().startswith('@import'))
        return '<style>'+data+'</style>'
    def js(match):
        data=(ROOT/'frontend'/match.group(1).lstrip('/')).read_text()
        return '<script>'+data+'</script>'
    html=re.sub(r'<link rel="stylesheet" href="(/assets/[^"]+)">',css,html)
    html=re.sub(r'<script src="(/assets/[^"]+)" defer></script>',js,html)
    static=client.post('/api/analyze',json={'code':SOURCE}).json()
    repair=client.post('/api/repair',json={'code':SOURCE,'runtime_stderr':TRACE,'runtime_exit_code':1}).json()
    verified=client.post('/api/verify',json={'code':repair['repaired_code'],'mode':'static'}).json()
    run={'status':'failed','stderr':TRACE,'stdout':'','exit_code':1,
         'message':'Program failed inside Docker','phase':'compile_or_run',
         'runtime_issues':[],
         'detected_language':'python'}
    # CI machines do not have Docker. The mocked run uses the actual
    # traceback-to-finding API implementation rather than inventing findings.
    from app.engine import runtime_issues
    run['runtime_issues']=runtime_issues(SOURCE,TRACE,1)
    responses={'/api/analyze':static,'/api/repair':repair,'/api/run':run,'/api/verify':verified,
               '/api/status':{'backend':'online','docker':{'available':False,'message':'Docker not present in browser smoke test'},'languages':['python','c','cpp','java','excel']}}
    mock='''<script>window.fetch=async function(path,opts){
      const results=MOCK_RESULTS;
      if(!(path in results))return {ok:false,status:404,json:async()=>({detail:'Unmocked endpoint '+path})};
      return {ok:true,status:200,json:async()=>results[path]};
    };</script>'''.replace('MOCK_RESULTS',json.dumps(responses).replace('</','<\\/'))
    html=html.replace('</head>',mock+'</head>')
    return html


def run():
    html=offline_html()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, executable_path=shutil.which('chromium') or shutil.which('google-chrome') or None, args=['--no-sandbox'])
        for width,height,device in ((1440,900,'desktop'),(390,844,'mobile')):
            page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
            errors=[]
            page.on('pageerror',lambda err:errors.append(str(err)))
            page.set_content(html,wait_until='domcontentloaded')
            assert 'VELOCITY 5.6' in page.title()
            page.locator('[data-scene="workspace"]').first.click()
            page.wait_for_timeout(600)
            assert page.locator('#scene-workspace').evaluate('(el)=>el.classList.contains("active")')
            page.locator('#code-editor').fill(SOURCE)
            page.locator('#analyze-run').click()
            page.wait_for_function("document.getElementById('repair-badge').textContent==='SUGGESTED'",timeout=10000)
            assert 'Runtime NameError' in page.locator('#diagnostics').inner_text()
            assert page.locator('#diagnostic-badge').inner_text()=='RUNTIME ERROR'
            assert 'len(students)' in page.locator('#after-code').inner_text()
            assert page.locator('#apply-repair').is_enabled()
            if device == 'mobile':
                page.locator('.repair-panel').scroll_into_view_if_needed()
                page.wait_for_timeout(250)
            page.screenshot(path=f'/mnt/data/AutoPatch_V56_{device}_runtime_repair.png',full_page=True)
            page.locator('#apply-repair').click()
            assert 'len(students)' in page.locator('#code-editor').input_value()
            assert page.locator('#apply-repair').is_disabled()
            page.locator('[data-scene="lab"]').first.click()
            page.wait_for_timeout(500)
            page.locator('#verify-static').click()
            page.wait_for_function("document.getElementById('verify-badge').textContent==='SYNTAX PASS'",timeout=10000)
            assert 'Syntax-only' in page.locator('#verify-summary').inner_text()
            page.locator('[data-scene="github"]').first.click()
            page.wait_for_timeout(500)
            assert page.locator('#github-publish').is_visible()
            assert 'len(students)' in page.locator('#github-code-preview').inner_text()
            assert not errors, f'{device} JavaScript errors: {errors}'
            overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
            print(device,'PASS; JS errors:',len(errors),'horizontal overflow:',overflow)
            page.close()
        browser.close()

if __name__=='__main__':
    run()
