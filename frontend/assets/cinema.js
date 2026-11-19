/* AutoPatch Cinema 5.0 — original cinematic frontend, real local FastAPI data. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = {scene: 'home', code: '', filename:'untitled', language:'auto', repair:null, busy:false, motion:true, runtime:null, runtimeCode:'', staticIssues:[], revision:0, snippets:[], history:[], applyingPatch:false};
  const scenes = ['home','workspace','lab','excel','career','github'];
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const escapeHTML = (input) => String(input ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const statusText = (status, el) => {el.textContent=status.toUpperCase();el.classList.toggle('passed',status==='passed'||status==='clean'||status==='syntax pass'||status==='suggested'||status==='applied');el.classList.toggle('failed',status==='failed'||status==='error'||status==='runtime error')};
  const safeMessage = (text,type='info') => {const row=document.createElement('p');row.className='message '+type;row.textContent=String(text);$('system-messages').prepend(row);while($('system-messages').children.length>6)$('system-messages').lastChild.remove()};
  async function api(path,payload) {
    let response;
    try {response=await fetch(path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});} catch (_) {throw new Error('Local backend unavailable. Start START_AUTOPATCH.bat in CMD.');}
    let data;try{data=await response.json()}catch(_){throw new Error('Server returned an invalid response.')}
    if(!response.ok){let d=data.detail||`HTTP ${response.status}`;if(Array.isArray(d))d=d.map(x=>x.msg).join('; ');throw new Error(String(d))}return data;
  }
  function haptic(){try{if(!reducedMotion.matches&&navigator.vibrate)navigator.vibrate(7)}catch(_){}}
  let changing=false;
  let switchReset=null;
  function switchScene(destination){
    if(!scenes.includes(destination)||changing||destination===state.scene)return;
    changing=true;haptic();
    const previousScene=$('scene-'+state.scene);
    const nextScene=$('scene-'+destination);
    const finish=()=>{previousScene.classList.remove('active','scene-exit');nextScene.classList.remove('scene-enter');changing=false;};
    document.querySelectorAll('.nav-link').forEach(b=>b.classList.toggle('selected',b.dataset.scene===destination));
    nextScene.scrollTop=0;
    state.scene=destination;
    if(!state.motion||reducedMotion.matches){
      previousScene.classList.remove('active','scene-exit');nextScene.classList.add('active');changing=false;return;
    }
    previousScene.classList.add('scene-exit');
    nextScene.classList.add('active','scene-enter');
    if(switchReset!==null)window.clearTimeout(switchReset);
    switchReset=window.setTimeout(()=>{finish();switchReset=null;},420);
  }
  document.querySelectorAll('[data-scene]').forEach(btn=>btn.addEventListener('click',()=>switchScene(btn.dataset.scene)));
  $('logo').addEventListener('click',()=>switchScene('home'));
  $('soundless').addEventListener('click',()=>{state.motion=!state.motion;document.body.classList.toggle('motion-off',!state.motion);$('soundless').textContent=state.motion?'MOTION ON':'MOTION OFF'});
  $('clear-messages').addEventListener('click',()=>{$('system-messages').replaceChildren();safeMessage('Message history cleared.')});
  function renderIssues(issues, executionFailed=false){
    const target=$('diagnostics');target.replaceChildren();
    if(!issues.length){const p=document.createElement('p');p.className='placeholder';p.textContent='No matching static issues. Run the code and tests to check for runtime and logic failures.';target.append(p)}
    for(const issue of issues){const el=document.createElement('article');el.className='finding';const title=document.createElement('h3');title.textContent=issue.title||issue.rule||'Potential issue';const detail=document.createElement('p');detail.textContent=issue.detail||'';const hint=document.createElement('small');hint.textContent=`LINE ${issue.line||'?'} • ${issue.suggestion||'Review manually.'}`;el.append(title,detail,hint);target.append(el)}
    statusText(executionFailed?'runtime error':issues.length?`${issues.length} found`:'no matches',$('diagnostic-badge'));
  }
  function showRepair(result){
    state.repair=result;
    $('before-code').textContent=result.original_code??$('code-editor').value;
    $('after-code').textContent=result.repaired_code??$('code-editor').value;
    $('apply-repair').disabled=!result.changed;
    statusText(result.changed?'suggested':'manual review',$('repair-badge'));
    $('repair-note').textContent=result.changed
      ? `${result.validation_message||'Review this proposed edit.'} Not runtime-verified: apply the patch, rerun and check tests.`
      : 'No safe automatic patch for the current code. Review diagnostics and the Docker traceback.';
  }
  $('code-editor').addEventListener('input',()=>{
    state.code=$('code-editor').value;
    state.revision++;
    const isPatch = state.applyingPatch;
    state.applyingPatch = false;
    if(!isPatch){
      state.runtime=null;state.runtimeCode='';state.repair=null;state.staticIssues=[];
      $('apply-repair').disabled=true;statusText('no patch',$('repair-badge'));
      $('before-code').textContent='Awaiting analysis.';$('after-code').textContent='No suggested changes yet.';
      $('repair-note').textContent='Automatic changes require review and independent verification.';
      statusText('ready',$('diagnostic-badge'));statusText('not run',$('execution-badge'));
      $('diagnostics').textContent='Code changed. Run Analyze + Run to refresh diagnostics.';
      $('stdout').textContent='Waiting for Docker execution.';$('stderr').textContent='No errors reported yet.';$('exit-code').textContent='EXIT —';
      statusText('idle',$('verify-badge'));$('verify-summary').textContent='Code changed. Rerun syntax validation or Docker tests.';
    }
    const lines=state.code.split('\n').length;
    $('line-numbers').textContent=Array.from({length:lines},(_,i)=>i+1).join('\n');
    $('editor-count').textContent=`${state.code.length} CHARS`;
  });
  $('code-editor').addEventListener('keydown',e=>{if(e.key==='Tab'){e.preventDefault();e.target.setRangeText('    ',e.target.selectionStart,e.target.selectionEnd,'end');e.target.dispatchEvent(new Event('input'))}if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();analyzeAndRun()}});
  $('code-editor').addEventListener('scroll',()=>{$('line-numbers').scrollTop=$('code-editor').scrollTop});
  $('clear-code').addEventListener('click',()=>{state.filename='untitled';$('editor-filename').textContent='UNTITLED / SOURCE';$('code-editor').value='';$('code-editor').dispatchEvent(new Event('input'));safeMessage('Editor cleared.')});
  $('code-file').addEventListener('change',async e=>{const f=e.target.files?.[0];if(!f)return;if(f.size>80000){safeMessage('File too large (maximum 20,000 characters).','error');return}try{const code=await f.text();if(code.length>20000){safeMessage('Maximum source length is 20,000 characters.','error');return}state.filename=f.name;$('editor-filename').textContent=f.name.toUpperCase();$('code-editor').value=code;$('code-editor').dispatchEvent(new Event('input'));safeMessage(`Loaded ${f.name}; no code executed.`,'success')}catch(error){safeMessage('Could not read the selected file.','error')}finally{e.target.value=''}});
  function codePayload(){return {code:$('code-editor').value,filename:state.filename,language:'auto',use_ai:Boolean($('ai-toggle')?.checked)}}
  function detection(data){const lang=data.detected_language||data.detection?.language;if(lang){state.language=lang;$('language-chip').textContent=`DETECTED ${lang.toUpperCase()}`}}
  async function analyzeAndRun(){
    if(!$('code-editor').value.trim()){safeMessage('Paste source code first.','error');return}
    if(state.busy)return;
    const payload=codePayload(),revision=state.revision;
    const current=()=>state.revision===revision && $('code-editor').value===payload.code;
    state.busy=true;$('analyze-run').disabled=true;$('generate-repair').disabled=true;
    statusText('scanning',$('diagnostic-badge'));statusText('checking',$('execution-badge'));
    try{
      try{
        const result=await api('/api/analyze',payload);
        if(!current())return;
        detection(result);state.staticIssues=result.issues||[];
        renderIssues(state.staticIssues);
        safeMessage(`${state.staticIssues.length} potential static issue(s). ${state.language.toUpperCase()} analysis complete.`,'info');
      }catch(error){if(!current())return;statusText('error',$('diagnostic-badge'));safeMessage(error.message,'error')}
      try{
        const run=await api('/api/run',payload);
        if(!current())return;
        detection(run);statusText(run.status||'unavailable',$('execution-badge'));
        $('stdout').textContent=run.stdout||'(No stdout)';
        $('stderr').textContent=run.stderr||run.message||'(No stderr)';
        $('exit-code').textContent=`EXIT ${run.exit_code??'—'}`;
        const failed=run.status==='failed'||run.status==='timeout';
        const runtimeIssues=run.runtime_issues||[];
        if(failed){
          const fallback={title:'Program execution failed',detail:run.message||'Nonzero exit code.',line:'?',suggestion:'Inspect STDERR / COMPILER for the real error.'};
          renderIssues([...state.staticIssues,...(runtimeIssues.length?runtimeIssues:[fallback])],true);
          safeMessage('Execution failed. The runtime error is now included in diagnostics.','error');
        }else{renderIssues(state.staticIssues);if(run.status==='unavailable')safeMessage(run.message,'info')}
        if(failed && run.exit_code!==null && state.language==='python'){
          state.runtime={runtime_stderr:run.stderr||'',runtime_exit_code:run.exit_code};
          state.runtimeCode=payload.code;
          // Prepare a reviewable patch automatically after a failed Docker run.
          try{
            const suggestion=await api('/api/repair',{...payload,...state.runtime});
            if(!current())return;
            showRepair(suggestion);
            safeMessage(suggestion.changed?'Potential repair ready for review. Rerun after applying.':'Runtime error detected; manual review may be required.',suggestion.changed?'success':'info');
          }catch(error){if(current())safeMessage('Could not prepare runtime repair: '+error.message,'error')}
        }
        refreshHistory();
      }catch(error){if(!current())return;statusText('error',$('execution-badge'));$('stderr').textContent=error.message;safeMessage(error.message,'error')}
    }finally{state.busy=false;$('analyze-run').disabled=false;$('generate-repair').disabled=false}
  }
  $('analyze-run').addEventListener('click',analyzeAndRun);
  $('generate-repair').addEventListener('click',async()=>{
    if(!$('code-editor').value.trim()){safeMessage('Paste source code first.','error');return}
    if(state.busy)return;
    const button=$('generate-repair'),payload=codePayload(),revision=state.revision;
    if(state.runtime && state.runtimeCode===payload.code)Object.assign(payload,state.runtime);
    button.disabled=true;
    try{
      const result=await api('/api/repair',payload);
      if(state.revision!==revision||$('code-editor').value!==payload.code)return;
      detection(result);showRepair(result);
      safeMessage(result.changed?'Suggested repair available. Review before applying.':'No confident repair available; source preserved.',result.changed?'success':'info');
      refreshHistory();
    }catch(error){safeMessage(error.message,'error')}finally{button.disabled=false}
  });
  $('apply-repair').addEventListener('click',()=>{
    if(!state.repair?.changed)return;
    if(state.repair.original_code!==$('code-editor').value){safeMessage('Editor changed since repair. Generate a new suggestion.','error');return}
    state.applyingPatch = true;
    $('code-editor').value=state.repair.repaired_code;
    $('code-editor').dispatchEvent(new Event('input'));
    $('before-code').textContent=state.repair.original_code;
    $('after-code').textContent=state.repair.repaired_code;
    statusText('applied',$('repair-badge'));
    $('repair-badge').classList.add('passed');
    $('repair-note').textContent='Suggested patch applied to editor! Click "ANALYZE + RUN" to execute and verify the fix.';
    $('apply-repair').disabled=true;
    safeMessage('Suggested patch applied, not yet verified. Click Analyze + Run, then run tests.','success');
  });
  async function verify(mode){const code=$('code-editor').value;if(!code.trim()){statusText('no code',$('verify-badge'));$('verify-summary').textContent='Paste code in Workspace first.';return}statusText('running',$('verify-badge'));
    try{const res=await api('/api/verify',{code,tests:$('test-code').value,filename:state.filename,language:'auto',mode});statusText(mode==='static'&&res.status==='passed'?'syntax pass':res.status||'unavailable',$('verify-badge'));$('verify-summary').textContent=(mode==='static'?'Syntax-only check — no code was executed. ':'')+(res.message||'');$('verify-output').textContent=res.output||'No output returned.';}
    catch(error){statusText('error',$('verify-badge'));$('verify-output').textContent=error.message}
  }
  $('verify-docker').addEventListener('click',()=>verify('docker'));$('verify-static').addEventListener('click',()=>verify('static'));
  const fileBase64=async(file)=>{if(file.size>2000000)throw new Error('File exceeds the 2 MB limit.');const buf=new Uint8Array(await file.arrayBuffer());let str='';for(let i=0;i<buf.length;i+=8192)str+=String.fromCharCode(...buf.subarray(i,i+8192));return btoa(str)};
  $('audit-excel').addEventListener('click',async()=>{const file=$('excel-file').files?.[0];if(!file){$('excel-results').textContent='Choose an XLSX workbook first.';return}statusText('auditing',$('excel-badge'));try{const data=await api('/api/workbook/analyze',{filename:file.name,data_base64:await fileBase64(file)});statusText('complete',$('excel-badge'));$('excel-results').replaceChildren();const summary=document.createElement('p');summary.className='placeholder';summary.textContent=`${data.total_formulas} formulas inspected • ${data.total_issues} issues found. Cached values may be stale; no formulas were executed.`;$('excel-results').append(summary);for(const issue of (data.issues||[]).slice(0,60)){const card=document.createElement('div');card.className='match-card';const heading=document.createElement('h3');heading.textContent=`${issue.sheet||''}!${issue.cell||'?'} — ${issue.title}`;const detail=document.createElement('p');detail.textContent=issue.suggestion||issue.detail||'';card.append(heading,detail);$('excel-results').append(card)}}catch(error){statusText('error',$('excel-badge'));$('excel-results').textContent=error.message}});
  $('career-match').addEventListener('click',async()=>{const cv=$('cv-file').files?.[0],jobs=$('jobs-file').files?.[0];if(!cv||!jobs){$('career-results').textContent='Upload both your CV and the job requirements workbook.';return}statusText('matching',$('career-badge'));try{const data=await api('/api/career/match',{cv_filename:cv.name,cv_base64:await fileBase64(cv),jobs_filename:jobs.name,jobs_base64:await fileBase64(jobs)});statusText('complete',$('career-badge'));$('career-results').replaceChildren();const summary=document.createElement('p');summary.className='placeholder';summary.textContent=`Compared ${data.jobs_checked} listed jobs. Matches reflect only the supplied criteria, not official eligibility.`;$('career-results').append(summary);for(const row of (data.results||[])){const card=document.createElement('div');card.className='match-card';const heading=document.createElement('h3');heading.textContent=`${row.company} — ${row.job_title}`;const score=document.createElement('strong');score.textContent=`${row.status.replaceAll('_',' ')} • Skill match ${row.skill_match_percent??'N/A'}%`;const detail=document.createElement('p');detail.textContent=[...(row.reasons||[]),...(row.unknowns||[])].join(' • ')||'Review the official posting.';card.append(heading,score,detail);$('career-results').append(card)}}catch(error){statusText('error',$('career-badge'));$('career-results').textContent=error.message}});

  async function loadSnippets(){
    const picker=$('snippet-picker');
    if(!picker)return;
    try{
      const res=await api('/api/snippets');
      state.snippets=res.snippets||[];
      picker.replaceChildren();
      const def=document.createElement('option');
      def.value='';
      def.textContent='LOAD SAMPLE...';
      picker.append(def);
      for(const s of state.snippets){
        const opt=document.createElement('option');
        opt.value=s.id;
        opt.textContent=`${s.title} (${(s.language||'py').toUpperCase()})`;
        picker.append(opt);
      }
    }catch(_){}
  }
  $('snippet-picker')?.addEventListener('change',e=>{
    const id=e.target.value;
    if(!id)return;
    const s=state.snippets.find(x=>x.id===id);
    if(!s)return;
    state.filename=s.filename||(s.language==='java'?'Main.java':s.language==='c'?'main.c':s.language==='cpp'?'main.cpp':s.language==='excel'?'formula.formula':'main.py');
    $('editor-filename').textContent=state.filename.toUpperCase();
    $('code-editor').value=s.code;
    if($('test-code')&&s.tests)$('test-code').value=s.tests;
    $('code-editor').dispatchEvent(new Event('input'));
    safeMessage(`Loaded sample: ${s.title}`,'info');
    e.target.value='';
  });

  async function refreshHistory(){
    try{
      const res=await api('/api/history');
      state.history=res.history||[];
      if($('history-count'))$('history-count').textContent=state.history.length;
      renderHistory(state.history);
    }catch(_){}
  }
  function renderHistory(items){
    const list=$('history-list');
    if(!list)return;
    list.replaceChildren();
    if(!items.length){
      const p=document.createElement('p');
      p.className='placeholder';
      p.textContent='No database execution history yet. Runs and repairs are saved automatically.';
      list.append(p);
      return;
    }
    for(const item of items.slice(0,30)){
      const card=document.createElement('div');
      card.className='history-card';
      const meta=document.createElement('div');
      meta.className='history-card-meta';
      const lang=document.createElement('span');
      lang.className='hist-lang';
      lang.textContent=(item.language||'PYTHON').toUpperCase();
      const act=document.createElement('span');
      act.className='hist-action';
      act.textContent=item.action;
      const st=document.createElement('span');
      st.className=`hist-status ${item.status==='passed'||item.status==='suggested'||item.status==='completed'?'passed':item.status==='failed'?'failed':''}`;
      st.textContent=item.status.toUpperCase();
      const time=document.createElement('small');
      time.textContent=item.timestamp?item.timestamp.split('T')[1].slice(0,8):'';
      meta.append(lang,act,st,time);
      const actions=document.createElement('div');
      actions.className='history-card-actions';
      const loadBtn=document.createElement('button');
      loadBtn.type='button';
      loadBtn.textContent='LOAD';
      loadBtn.addEventListener('click',()=>{
        state.filename=item.filename||'untitled.py';
        $('editor-filename').textContent=state.filename.toUpperCase();
        $('code-editor').value=item.repaired_code&&item.action==='repair'?item.repaired_code:item.code;
        $('code-editor').dispatchEvent(new Event('input'));
        safeMessage(`Loaded from history record #${item.id}.`,'info');
        $('history-panel')?.classList.remove('open');
      });
      actions.append(loadBtn);
      card.append(meta,actions);
      list.append(card);
    }
  }
  $('history-toggle')?.addEventListener('click',()=>{
    const panel=$('history-panel');
    if(!panel)return;
    const isOpen=panel.classList.toggle('open');
    panel.setAttribute('aria-hidden',String(!isOpen));
    if(isOpen)refreshHistory();
  });
  $('close-history-btn')?.addEventListener('click',()=>{
    $('history-panel')?.classList.remove('open');
    $('history-panel')?.setAttribute('aria-hidden','true');
  });
  $('clear-history-btn')?.addEventListener('click',async()=>{
    try{
      await fetch('/api/history',{method:'DELETE'});
      refreshHistory();
      safeMessage('Database history cleared.','info');
    }catch(err){safeMessage(err.message,'error')}
  });

  async function status(){
    try{
      const data=await api('/api/status');
      $('server-status').textContent='ENGINE ONLINE';
      $('live-dot').classList.add('online');
      $('hero-engine').textContent='SYSTEM ONLINE';
      $('docker-indicator').textContent=data.docker.available?'DOCKER READY':'DOCKER OPTIONAL';
      if($('ai-toggle-text')){
        $('ai-toggle-text').textContent=data.ai_configured?`AI (${(data.ai_provider||'READY').toUpperCase()})`:'AI ASSIST';
      }
      refreshHistory();
      loadSnippets();
    }catch(_){
      $('server-status').textContent='ENGINE OFFLINE';
      $('hero-engine').textContent='BACKEND OFFLINE';
      $('docker-indicator').textContent='DOCKER STATUS UNKNOWN';
    }
  }
  status();
})();