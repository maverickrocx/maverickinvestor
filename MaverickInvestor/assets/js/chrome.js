// assets/js/chrome.js — the shared nav and footer for every page.
//
// This is a static site with no build step, so there are no includes. Instead
// each page writes <mi-nav></mi-nav> and <mi-footer></mi-footer> where the
// chrome belongs and loads this file (synchronously) in <head>. Because the
// custom elements are defined before the parser reaches them, each one renders
// the moment it is parsed — no flash, no layout shift. Edit the nav and footer
// here, once, for the whole site.
(function () {
  var LINKS = [
    ['index.html', 'Home'],
    ['tools.html', 'Tools &amp; Goals'],
    ['mf-advisor.html', 'MF Advisor'],
    ['stock-screener.html', 'Stock Screener'],
    ['learn.html', 'Learn'],
    ['about.html', 'About']
  ];
  var EMAIL = 'jileshkadi@gmail.com';

  function currentPage() {
    var p = location.pathname.split('/').pop();
    return p === '' ? 'index.html' : p;
  }

  var SUN = '<svg class="ico-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>';
  var MOON = '<svg class="ico-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M20 14a8 8 0 1 1-9.9-9.9A7 7 0 0 0 20 14z"/></svg>';
  var SHIELD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>';
  var LINKEDIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/></svg>';
  var MAIL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>';

  function logo() {
    return '<span class="logo-icon"><img src="assets/logo.png" alt="" width="46" height="46"></span>' +
           '<span class="logo-word"><strong>Maverick</strong> Investor</span>';
  }

  function navHTML() {
    var here = currentPage();
    var links = LINKS.map(function (l) {
      return '<a href="' + l[0] + '"' + (l[0] === here ? ' aria-current="page"' : '') + '>' + l[1] + '</a>';
    }).join('');
    return '<header class="nav">' +
      '<div class="nav-inner">' +
        '<a class="logo" href="index.html" aria-label="Maverick Investor — home">' + logo() + '</a>' +
        '<nav class="nav-links" id="navLinks" aria-label="Main">' + links + '</nav>' +
        '<div class="nav-act">' +
          '<button class="icon-btn" type="button" data-theme-toggle aria-label="Switch to dark mode">' + SUN + MOON + '</button>' +
          '<button class="nav-toggle" type="button" aria-label="Toggle menu" aria-expanded="false" aria-controls="navLinks">&#9776;</button>' +
        '</div>' +
      '</div>' +
    '</header>';
  }

  function col(title, items) {
    return '<div class="footer-col"><h4>' + title + '</h4><ul>' +
      items.map(function (i) { return '<li><a href="' + i[0] + '"' + (i[2] || '') + '>' + i[1] + '</a></li>'; }).join('') +
      '</ul></div>';
  }

  function footerHTML() {
    return '<footer class="site-footer">' +
      '<div class="footer-inner">' +
        '<div class="footer-brand">' +
          '<a class="logo" href="index.html" aria-label="Maverick Investor — home">' + logo() + '</a>' +
          '<div class="footer-tagline"><em>Maverick</em> thinking. Investor returns.</div>' +
          '<p>Unbiased, research-backed guidance on mutual funds, insurance and retirement planning for Indian investors.</p>' +
          '<span class="sebi-badge">' + SHIELD + ' SEBI investor-education compliant</span>' +
          '<div class="social-row">' +
            '<a href="https://www.linkedin.com/in/jilesh/" target="_blank" rel="noopener" class="social-btn" title="LinkedIn" aria-label="LinkedIn">' + LINKEDIN + '</a>' +
            '<a href="mailto:' + EMAIL + '" class="social-btn" title="Email" aria-label="Email">' + MAIL + '</a>' +
          '</div>' +
        '</div>' +
        col('Navigate', LINKS) +
        col('Tools', [
          ['tools.html', 'SIP Calculator'], ['tools.html', 'Retirement Planner'], ['tools.html', 'Goal Tracker'],
          ['mf-advisor.html', 'MF Advisor'], ['stock-screener.html', 'Stock Screener']
        ]) +
        col('Learn', [
          ['learn.html#mf', 'Mutual Fund Basics'], ['learn.html#ins', 'Insurance Basics'], ['learn.html#nps', 'NPS Guide'],
          ['about.html', 'About Us'], ['#', 'Contact', ' data-contact']
        ]) +
      '</div>' +
      '<div class="footer-legal">' +
        '<span>© ' + new Date().getFullYear() + ' Maverick Investor. All rights reserved.</span>' +
        '<span>Not SEBI-registered · Educational use only · Not investment advice</span>' +
      '</div>' +
    '</footer>' +
    '<div class="email-popup" id="email-popup" role="dialog" aria-modal="true" aria-label="Contact">' +
      '<div class="email-popup-card">' +
        '<p class="ep-label">Get in touch</p>' +
        '<p class="ep-addr">' + EMAIL + '</p>' +
        '<div class="ep-btns">' +
          '<button type="button" class="btn btn-primary" data-ep-copy>Copy</button>' +
          '<button type="button" class="btn btn-secondary" data-ep-close>Close</button>' +
        '</div>' +
        '<p class="ep-ok" id="copy-confirm">Copied to clipboard!</p>' +
      '</div>' +
    '</div>';
  }

  function wireNav(root) {
    var toggle = root.querySelector('.nav-toggle');
    var links = root.querySelector('.nav-links');
    if (!toggle || !links) return;
    function set(open) {
      links.classList.toggle('open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    toggle.addEventListener('click', function (e) { e.stopPropagation(); set(!links.classList.contains('open')); });
    links.addEventListener('click', function () { set(false); });
    document.addEventListener('click', function (e) { if (!root.contains(e.target)) set(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') set(false); });
  }

  function wireFooter(root) {
    var pop = root.querySelector('#email-popup');
    if (!pop) return;
    function show() { pop.classList.add('open'); pop.querySelector('#copy-confirm').style.opacity = '0'; }
    function hide() { pop.classList.remove('open'); }
    // Kept global: older pages call showEmailPopup() from inline handlers.
    window.showEmailPopup = show;
    window.closeEmailPopup = hide;
    root.querySelectorAll('[data-contact]').forEach(function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); show(); });
    });
    pop.addEventListener('click', function (e) { if (e.target === pop) hide(); });
    pop.querySelector('[data-ep-close]').addEventListener('click', hide);
    pop.querySelector('[data-ep-copy]').addEventListener('click', function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(EMAIL).then(function () {
        var c = pop.querySelector('#copy-confirm');
        c.style.opacity = '1';
        setTimeout(function () { c.style.opacity = '0'; }, 2500);
      });
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') hide(); });
  }

  function define(name, render, wire) {
    if (!window.customElements || customElements.get(name)) return;
    customElements.define(name, class extends HTMLElement {
      connectedCallback() {
        if (this.dataset.rendered) return;
        this.dataset.rendered = '1';
        this.innerHTML = render();
        wire(this);
      }
    });
  }
  define('mi-nav', navHTML, wireNav);
  define('mi-footer', footerHTML, wireFooter);
})();
