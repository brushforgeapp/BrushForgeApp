// Smooth scroll for in-page anchors (supports nested elements)
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const id = a.getAttribute('href');
  if (!id || id.length <= 1) return;
  const el = document.querySelector(id);
  if (!el) return;
  e.preventDefault();
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  history.pushState(null, '', id);
});

// FAQ accordion with ARIA state
document.addEventListener('click', (e) => {
  const q = e.target.closest('.faq .q');
  if (!q) return;
  const item = q.closest('.item');
  const open = !item.classList.contains('open');
  document.querySelectorAll('.faq .item').forEach(i => i.classList.remove('open'));
  item.classList.toggle('open', open);
  q.setAttribute('aria-expanded', open ? 'true' : 'false');
});

// Share button (Web Share API with clipboard fallback)
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-share]');
  if (!btn) return;
  e.preventDefault();
  const shareData = {
    title: 'BrushForge — Paint converter & toolkit',
    text: "I'm testing this app for miniature painters. Join the TestFlight beta:",
    url: 'https://testflight.apple.com/join/2jnGZJss'
  };
  try {
    if (navigator.share) {
      await navigator.share(shareData);
    } else if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(shareData.url);
      btn.textContent = 'Link copied ✓';
      setTimeout(() => (btn.textContent = 'Share BrushForge'), 1500);
    }
  } catch {
    /* no-op */
  }
});

// Resilient mailto (explicit navigation to satisfy some mobile browsers)
document.addEventListener('click', (e) => {
  const m = e.target.closest('[data-mailto]');
  if (!m) return;
  const href = m.getAttribute('href');
  if (!href?.startsWith('mailto:')) return;
  // Defer to allow default processing
  setTimeout(() => { window.location.href = href; }, 0);
});

// Reveal on Scroll
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('active');
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));

// Dynamic Behaviors (Cookie Banner & 3D Cards)
document.addEventListener('DOMContentLoaded', () => {
  const banner = document.getElementById('cookie-banner');
  const btn = document.getElementById('accept-cookies');
  
  if (banner && btn && !localStorage.getItem('cookiesAccepted')) {
    setTimeout(() => banner.classList.add('show'), 1500);
    
    btn.addEventListener('click', () => {
      localStorage.setItem('cookiesAccepted', 'true');
      banner.classList.remove('show');
    });
  }
  
  // Initialize Vanilla Tilt on desktop for Cards and Phone Frames
  if (typeof VanillaTilt !== 'undefined' && window.matchMedia("(min-width: 768px)").matches) {
    VanillaTilt.init(document.querySelectorAll(".card, .phone-frame"), {
      max: 5,
      speed: 400,
      glare: true,
      "max-glare": 0.15,
      scale: 1.02,
      transition: true
    });
  }
});

