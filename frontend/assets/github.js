(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const preview = () => {const code = $('code-editor').value; $('github-code-preview').textContent=code || 'No code loaded. Open Workspace and paste or upload a file.'; $('github-file-count').textContent=code ? `${code.length} CHARS` : 'EMPTY'; const name=$('editor-filename').textContent; if(name && !name.startsWith('UNTITLED') && $('github-filename').value==='main.py')$('github-filename').value=name.toLowerCase();};
  // A hosted preview never asks visitors to supply GitHub credentials.
  let publishingDisabled = false;
  async function applyPublicPreviewGuard(){
    try {
      const response = await fetch('/api/status');
      if (!response.ok) return;
      const status = await response.json();
      if (!status.public_demo) return;
      publishingDisabled = true;
      $('github-token').value = '';
      $('github-token').disabled = true;
      $('github-publish').disabled = true;
      $('github-badge').textContent = 'LOCAL ONLY';
      $('github-result').textContent = 'GitHub publishing is disabled on the public preview. Run AutoPatch locally to publish.';
    } catch (_) { /* The backend also blocks publishing in public-preview mode. */ }
  }
  applyPublicPreviewGuard();
  $('github-preview').addEventListener('click',preview);
  document.querySelectorAll('[data-scene="github"]').forEach(button=>button.addEventListener('click',preview));
  $('github-publish').addEventListener('click', async () => {
    const button=$('github-publish'),result=$('github-result');
    if (publishingDisabled) { result.textContent='GitHub publishing is available only in the local version.'; return; }
    const code=$('code-editor').value;
    if(!code.trim()){result.textContent='Paste code into Workspace before publishing.';return;}
    if(!$('github-token').value.trim()){result.textContent='Enter a GitHub token first.';return;}
    button.disabled=true;$('github-badge').textContent='PUBLISHING';result.textContent='Contacting GitHub securely via local backend…';
    const payload={token:$('github-token').value.trim(),repository:$('github-repo').value.trim(),owner:$('github-owner').value.trim(),filename:$('github-filename').value.trim(),code,create_new:$('github-create').checked,private:$('github-private').checked,message:$('github-message').value.trim()};
    try{const response=await fetch('/api/github/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok){const d=data.detail;throw new Error(Array.isArray(d)?d.map(x=>x.msg).join('; '):String(d||'GitHub publish failed'));}
      $('github-badge').textContent='PUBLISHED';result.replaceChildren();const msg=document.createElement('p');msg.textContent='Code published successfully!';const link=document.createElement('a');link.href=data.repository_url;link.textContent='OPEN GITHUB REPOSITORY ↗';link.target='_blank';link.rel='noopener noreferrer';result.append(msg,link);
    }catch(err){$('github-badge').textContent='ERROR';result.textContent=err.message||'Could not publish.';}finally{button.disabled=publishingDisabled;$('github-token').value='';}
  });
})();
