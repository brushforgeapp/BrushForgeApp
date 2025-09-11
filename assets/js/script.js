
// Smooth scroll for in-page anchors
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const id = a.getAttribute('href');
  if (id.length > 1 && document.querySelector(id)) {
    e.preventDefault();
    document.querySelector(id).scrollIntoView({behavior:'smooth', block:'start'});
    history.pushState(null, '', id);
  }
});



// FAQ accordion
document.addEventListener('click', (e) => {
  const q = e.target.closest('.faq .q');
  if (!q) return;
  const item = q.closest('.item');
  item.classList.toggle('open');
});



// Share button
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-share]');
  if (!btn) return;
  e.preventDefault();
  const shareData = {
    title: 'BrushForge — Paint converter & toolkit',
    text: 'I'm testing this app for miniature painters. Join the TestFlight beta:',
    url: 'https://testflight.apple.com/join/2jnGZJss'
  };
  try {
    if (navigator.share) {
      await navigator.share(shareData);
    } else {
      await navigator.clipboard.writeText(shareData.url);
      btn.textContent = 'Link copied ✓';
      setTimeout(() => (btn.textContent = 'Share BrushForge'), 1500);
    }
  } catch {}
});


// Accessibility for FAQ
document.addEventListener('click', (e) => {
  const q = e.target.closest('.faq .q');
  if (!q) return;
  const item = q.closest('.item');
  const open = item.classList.toggle('open');
  q.setAttribute('aria-expanded', open ? 'true' : 'false');
});
