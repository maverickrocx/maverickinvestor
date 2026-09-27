// assets/js/reveal.js — tiles enter the way the hero portfolio card does:
// fade up 30px from 97% scale, 0.8s ease-out, once, as each scrolls into view.
//
// Tiles start hidden via CSS (html.rv, set by the no-flash script in <head>,
// skipped for prefers-reduced-motion), so nothing flashes before this runs.
// Tiles that a script re-renders (the fund tables refresh every 5 minutes)
// are recognised by data-group and shown at once instead of replaying.
(function () {
  var SEL = '.hero-sip-calc, .fund-cat-block, .why-card, .ret-cta-card, .app-grid, .disclaimer';
  var root = document.documentElement;
  if (!root.classList.contains('rv')) return;

  var seenKeys = {};
  var queue = [];
  var flushTimer = null;
  var started = false;
  var firstBatch = true;

  function done(el) {
    el.classList.add('is-in', 'is-done');
    el.style.transitionDelay = '';
    if (el.dataset.group) seenKeys[el.dataset.group] = true;
  }

  function play(el, delay) {
    el.style.transitionDelay = delay + 'ms';
    el.classList.add('is-in');
    if (el.dataset.group) seenKeys[el.dataset.group] = true;
    var finish = function (e) {
      if (e && e.target !== el) return;
      el.removeEventListener('transitionend', finish);
      done(el);
    };
    el.addEventListener('transitionend', finish);
    setTimeout(finish, 1200 + delay);   // in case transitionend never fires
  }

  // Tiles that enter together are staggered 80ms apart, in document order.
  // The first batch (the hero) waits 0.3s, like the portfolio card's GSAP delay.
  function flush() {
    flushTimer = null;
    var base = firstBatch ? 300 : 0;
    firstBatch = false;
    queue.sort(function (a, b) {
      return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    }).forEach(function (el, i) { play(el, base + i * 80); });
    queue = [];
  }

  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      io.unobserve(en.target);
      queue.push(en.target);
    });
    if (queue.length && !flushTimer) flushTimer = setTimeout(flush, 30);
  }, { rootMargin: '0px 0px -8% 0px' }) : null;

  function watch(el) {
    if (el.classList.contains('is-in')) return;
    if (!io || (el.dataset.group && seenKeys[el.dataset.group])) { done(el); return; }
    io.observe(el);
  }

  function start() {
    if (started) return;
    started = true;
    document.querySelectorAll(SEL).forEach(watch);
    // Pick up tiles rendered later by scripts (runs before the next paint).
    new MutationObserver(function (muts) {
      muts.forEach(function (m) {
        m.addedNodes.forEach(function (n) {
          if (n.nodeType !== 1) return;
          if (n.matches(SEL)) watch(n);
          n.querySelectorAll && n.querySelectorAll(SEL).forEach(watch);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  }

  // Wait for the intro video (if any) to start fading, so the first tiles
  // animate where the reader can see them.
  if (window.miAfterIntro) window.miAfterIntro(start); else start();
  // Safety net: never leave tiles hidden.
  setTimeout(function () {
    start();
    document.querySelectorAll(SEL).forEach(function (el) {
      if (!el.classList.contains('is-in') && el.getBoundingClientRect().top < innerHeight) play(el, 0);
    });
  }, 14000);
})();
