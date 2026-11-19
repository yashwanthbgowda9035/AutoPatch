/* Motion particles and gentle pointer parallax; no network or simulated code output. */
(() => {
  'use strict';
  const canvas = document.getElementById('motion-particles');
  const scene = document.getElementById('scene-home');
  const sphere = document.querySelector('.kinetic-sphere');
  if (!canvas || !scene || !sphere) return;
  const ctx = canvas.getContext('2d', { alpha: true });
  if (!ctx) return;
  const media = window.matchMedia('(prefers-reduced-motion: reduce)');
  const cursor = document.createElement('div');
  cursor.id = 'motion-cursor'; cursor.classList.add('is-idle');
  document.body.append(cursor);
  let points = [], width = 1, height = 1, frame = 0, raf = 0, lastFrame = 0;
  let pointerX = .5, pointerY = .5, smoothX = .5, smoothY = .5;
  const motionEnabled = () => !media.matches && !document.body.classList.contains('motion-off') && scene.classList.contains('active') && !document.hidden;
  const resize = () => {
    const bounds = canvas.getBoundingClientRect();
    width = Math.max(1, bounds.width); height = Math.max(1, bounds.height);
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    // Keep the particle count modest for low-end laptops.
    const count = Math.min(64, Math.max(26, Math.floor(width * height / 24000)));
    points = Array.from({length: count}, (_, i) => ({x: (i * 73.37 % 101) / 101 * width,
      y: (i * 49.83 % 101) / 101 * height, phase: i * 1.618,
      speed: .16 + (i % 7) * .045, radius: .6 + (i % 4) * .34}));
  };
  const move = (event) => {
    const b = scene.getBoundingClientRect();
    pointerX = Math.min(1, Math.max(0, (event.clientX - b.left) / b.width));
    pointerY = Math.min(1, Math.max(0, (event.clientY - b.top) / b.height));
    cursor.style.left = `${event.clientX}px`; cursor.style.top = `${event.clientY}px`;
    cursor.classList.remove('is-idle');
  };
  scene.addEventListener('pointermove', move, {passive:true});
  scene.addEventListener('pointerleave', () => {pointerX = .5; pointerY = .5; cursor.classList.add('is-idle')});
  const draw = (now) => {
    raf = 0;
    if (!motionEnabled()) return;
    // Cap the decorative canvas at 30fps; CSS transforms remain smooth at display refresh rate.
    if (now - lastFrame < 32) { raf = requestAnimationFrame(draw); return; }
    lastFrame = now;
    frame++;
    smoothX += (pointerX - smoothX) * .042;
    smoothY += (pointerY - smoothY) * .042;
    sphere.style.setProperty('--mx', `${(smoothX - .5) * 35}px`);
    sphere.style.setProperty('--my', `${(smoothY - .5) * 26}px`);
    ctx.clearRect(0, 0, width, height);
    for (const p of points) {
      const yy = (p.y - frame * p.speed % (height + 30) + height + 30) % (height + 30);
      const x = p.x + Math.sin(frame * .007 + p.phase) * 14 + (smoothX - .5) * 14;
      const alpha = .2 + .48 * (Math.sin(frame * .018 + p.phase) + 1) / 2;
      ctx.beginPath();ctx.arc(x, yy, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(207,255,195,${alpha.toFixed(3)})`;ctx.fill();
      if (frame % 3 === 0 && p.radius > 1.1) {
        ctx.beginPath(); ctx.moveTo(x, yy + 3); ctx.lineTo(x + .5, yy + 13);
        ctx.strokeStyle = 'rgba(193,253,186,.13)';ctx.stroke();
      }
    }
    raf = requestAnimationFrame(draw);
  };
  const sync = () => {
    if (motionEnabled()) {if (!raf) raf = requestAnimationFrame(draw)}
    else if (raf) {cancelAnimationFrame(raf);raf = 0;cursor.classList.add('is-idle')}
  };
  if ('ResizeObserver' in window) new ResizeObserver(resize).observe(canvas); else window.addEventListener('resize', resize);
  const observer = new MutationObserver(sync);
  observer.observe(scene, {attributes:true,attributeFilter:['class']});
  observer.observe(document.body, {attributes:true,attributeFilter:['class']});
  document.addEventListener('visibilitychange', sync);
  media.addEventListener?.('change', sync);
  resize();sync();
})();
