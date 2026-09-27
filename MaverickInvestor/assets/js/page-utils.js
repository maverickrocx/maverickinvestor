// assets/js/page-utils.js — floating back + back-to-top circles on every page.
//
// Back shows only when the previous page was on this site (so it never sends
// a reader off the website) and never on the Home page. Back-to-top only fades
// in once the reader has scrolled past the fold.
(function () {
  var wrap = document.createElement('div');
  wrap.className = 'pageutils';

  var back = document.createElement('button');
  back.type = 'button';
  back.setAttribute('aria-label', 'Go back');
  back.title = 'Back';
  back.textContent = '←';
  back.addEventListener('click', function () { history.back(); });

  var top = document.createElement('button');
  top.type = 'button';
  top.setAttribute('aria-label', 'Back to top');
  top.title = 'Back to top';
  top.textContent = '↑';
  top.addEventListener('click', function () {
    var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
  });

  wrap.appendChild(back);
  wrap.appendChild(top);
  document.body.appendChild(wrap);

  var file = location.pathname.split('/').pop();
  var isHome = file === '' || file === 'index.html';
  var fromSite = false;
  try { fromSite = !!document.referrer && new URL(document.referrer).origin === location.origin; } catch (e) {}
  if (isHome || !fromSite) back.remove();
  else back.classList.add('show');
  function update() { top.classList.toggle('show', window.scrollY > 300); }
  window.addEventListener('scroll', update, { passive: true });
  update();
})();
