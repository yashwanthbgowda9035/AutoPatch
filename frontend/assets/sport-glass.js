/* AutoPatch Sport Glass: local visual enhancements, no network and no fake outputs. */
(() => {
  'use strict';
  const dock = document.querySelector('[data-sport-dock]');
  const preview = document.getElementById('sport-dock-preview');
  const glow = document.getElementById('sports-pointer-glow');
  if (!dock || !preview) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const pointer = matchMedia('(hover: hover) and (pointer: fine)');
  const nav = [...dock.querySelectorAll('button[data-scene]')];
  const metadata = {
    home: ['01 / 06', 'EXPERIENCE', 'Live kinetic interface · your project in motion'],
    workspace: ['02 / 06', 'CODE WORKSPACE', 'Analyze code · review repairs · see real output'],
    lab: ['03 / 06', 'VERIFICATION LAB', 'Python tests and isolated Docker verification'],
    excel: ['04 / 06', 'EXCEL INSPECTOR', 'Static formula diagnostics for XLSX files'],
    career: ['05 / 06', 'CAREER MATCHER', 'Compare CV evidence against supplied job criteria'],
    github: ['06 / 06', 'GITHUB STUDIO', 'Publish your repaired source to a GitHub repository'],
  };
  let active = null;
  let delay = 0;
  let raf = 0;
  const animated = () => pointer.matches && !reduced.matches && !document.body.classList.contains('motion-off');
  const hide = () => {clearTimeout(delay);active=null;preview.classList.remove('open');preview.setAttribute('aria-hidden','true');};
  const display = (button) => {
    if (!button || !animated()) {hide();return;}
    const data=metadata[button.dataset.scene];if (!data) return;
    active=button;
    preview.querySelector('.preview-num').textContent=data[0];
    preview.querySelector('.preview-copy strong').textContent=data[1];
    preview.querySelector('.preview-copy small').textContent=data[2];
    preview.querySelector('.preview-watermark').textContent=button.dataset.scene==='home'?'AP':data[1].slice(0,2);
    const box=button.getBoundingClientRect();
    const left=Math.min(innerWidth-150,Math.max(150,box.left+box.width/2));
    preview.style.left=left+'px';
    preview.style.top=Math.max(78,Math.min(innerHeight-260,box.bottom+22))+'px';
    preview.classList.add('open');preview.setAttribute('aria-hidden','true');
  };
  const restoreDock = () => {nav.forEach(b=>{b.style.setProperty('--dock-scale','1');b.style.setProperty('--dock-lift','0px')})};
  const magnify = (x) => {
    if(!animated()) {restoreDock();return;}
    nav.forEach((b)=>{
      const r=b.getBoundingClientRect(), d=Math.abs(x-(r.left+r.width/2));
      const strength=Math.max(0,1-d/190);
      b.style.setProperty('--dock-scale',(1+strength*.24).toFixed(3));
      b.style.setProperty('--dock-lift',(-7*strength).toFixed(2)+'px');
    });
  };
  nav.forEach(button=>{
    button.addEventListener('pointerenter',()=>{if(!animated())return;clearTimeout(delay);delay=setTimeout(()=>display(button),95)});
    button.addEventListener('focus',()=>{if(!reduced.matches && pointer.matches)display(button)});
    button.addEventListener('blur',()=>{hide()});
    button.addEventListener('click',()=>{hide();restoreDock()});
  });
  dock.addEventListener('pointermove',e=>magnify(e.clientX),{passive:true});
  dock.addEventListener('pointerleave',()=>{hide();restoreDock()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape')hide()});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)hide()});
  const motionButton=document.getElementById('soundless');
  motionButton?.addEventListener('click',()=>{if(document.body.classList.contains('motion-off')){hide();restoreDock()}});
  /* Magnetic buttons with pointer-directed specular highlights. */
  const magnetSelector='.main-cta,.sub-cta,.action-primary,.action-secondary,.minimal-btn,.quiet-button,.explore-next';
  document.querySelectorAll(magnetSelector).forEach(el=>{
    el.addEventListener('pointermove',event=>{
      if(!animated())return;
      const r=el.getBoundingClientRect(),dx=event.clientX-r.left-r.width/2,dy=event.clientY-r.top-r.height/2;
      el.style.setProperty('--mag-x',(dx*.085).toFixed(1)+'px');
      el.style.setProperty('--mag-y',(dy*.12).toFixed(1)+'px');
      el.style.setProperty('--light-x',((event.clientX-r.left)/r.width*100).toFixed(1)+'%');
      el.style.setProperty('--light-y',((event.clientY-r.top)/r.height*100).toFixed(1)+'%');
    },{passive:true});
    el.addEventListener('pointerleave',()=>{el.style.setProperty('--mag-x','0px');el.style.setProperty('--mag-y','0px')});
  });
  /* A tiny, bounded 3D tilt for glass panels. Avoid interfering with editors. */
  document.querySelectorAll('.glass-panel').forEach(panel=>{
    panel.addEventListener('pointermove',e=>{
      if(!animated())return;
      const r=panel.getBoundingClientRect();
      const x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
      panel.style.setProperty('--tilt-x',(-y*1.3).toFixed(2)+'deg');
      panel.style.setProperty('--tilt-y',(x*1.3).toFixed(2)+'deg');
      panel.style.setProperty('--light-x',((x+.5)*100).toFixed(1)+'%');
      panel.style.setProperty('--light-y',((y+.5)*100).toFixed(1)+'%');
    },{passive:true});
    panel.addEventListener('pointerleave',()=>{panel.style.setProperty('--tilt-x','0deg');panel.style.setProperty('--tilt-y','0deg')});
  });
  /* Cursor light uses a single animation frame; no DOM additions per event. */
  document.addEventListener('pointermove',e=>{
    if(!glow || !animated())return;
    const x=e.clientX,y=e.clientY;
    if(raf)return;
    raf=requestAnimationFrame(()=>{glow.style.transform='translate3d('+x+'px,'+y+'px,0) translate(-50%,-50%)';document.body.classList.add('sports-pointer-visible');raf=0});
  },{passive:true});
  document.addEventListener('pointerleave',()=>document.body.classList.remove('sports-pointer-visible'));
})();
