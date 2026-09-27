// assets/js/page-utils.js — floating back + back-to-top circles on every page.
//
// Back shows whenever there is history to go back to; back-to-top only fades
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

  back.classList.toggle('show', window.history.length > 1);
  function update() { top.classList.toggle('show', window.scrollY > 300); }
  window.addEventListener('scroll', update, { passive: true });
  update();
})();
