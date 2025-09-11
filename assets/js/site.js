
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

// FAQ accordion (single handler with ARIA)
document.addEventListener('click', (e) => {
  const q = e.target.closest('.faq .q');
  if (!q) return;
  const item = q.closest('.item');
  const open = !item.classList.contains('open');
  document.querySelectorAll('.faq .item').forEach(i => i.classList.remove('open'));
  item.classList.toggle('open', open);
  q.setAttribute('aria-expanded', open ? 'true' : 'false');
});

// Share button
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-share]');
  if (!btn) return;
  e.preventDefault();
  const shareData = {
    title: 'BrushForge — Paint converter & toolkit',
    text: 'I\'m testing this app for miniature painters. Join the TestFlight beta:',
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

// Resilient mailto (fallback)
document.addEventListener('click', (e) => {
  const m = e.target.closest('[data-mailto]');
  if (!m) return;
  const href = m.getAttribute('href');
  if (href && href.startsWith('mailto:')) {
    setTimeout(() => { window.location.href = href; }, 0);
  }
});
