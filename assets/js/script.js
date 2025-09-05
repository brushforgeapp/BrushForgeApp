// Year in footer
document.getElementById('year').textContent = new Date().getFullYear();

// Mobile nav toggle
const toggle = document.querySelector('.nav-toggle');
const nav = document.querySelector('.site-nav');
if (toggle) {
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });
}

// Reveal-on-scroll
const reveals = document.querySelectorAll('.reveal');
const io = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('in');
      io.unobserve(e.target);
    }
  });
}, { threshold: 0.15 });
reveals.forEach(el => io.observe(el));

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', (e) => {
    const id = a.getAttribute('href');
    if (id.length > 1) {
      e.preventDefault();
      document.querySelector(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      nav.classList.remove('open');
      toggle?.setAttribute('aria-expanded', 'false');
    }
  });
});

// Newsletter demo
function subscribe(e){
  const form = e.target.closest('form');
  const email = form?.querySelector('input[type="email"]')?.value || '';
  if (!email) return;
  alert(`Thanks! We'll keep you posted at: ${email}`);
  form.reset();
}
window.subscribe = subscribe;
