// assets/js/theme.js — light/dark toggle. Light is the default; the no-flash
// read of localStorage 'mi-theme' happens inline at the top of each page's <head>.
(function () {
  var KEY = 'mi-theme';
  function label(t) {
    document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
      b.setAttribute('aria-label', t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    });
  }
  function setTheme(t) {
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
    try { localStorage.setItem(KEY, t); } catch (e) {}
    label(t);
  }
  var current = function () {
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  };
  label(current());
  document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () { setTheme(current() === 'dark' ? 'light' : 'dark'); });
  });
})();
