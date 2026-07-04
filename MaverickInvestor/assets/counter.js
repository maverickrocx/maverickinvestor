(function (global) {
  function initMaverickCounters(selector) {
    if (typeof gsap === 'undefined') return;
    document.querySelectorAll(selector).forEach(function (el) {
      var target = parseInt(el.dataset.count, 10);
      var prefix = el.dataset.prefix || '';
      var suffix = el.dataset.suffix || '';
      var obj = { val: 0 };
      gsap.to(obj, {
        val: target,
        duration: 1.8,
        delay: 0.6,
        ease: 'power2.out',
        onUpdate: function () {
          el.textContent = prefix + Math.round(obj.val).toLocaleString('en-IN') + suffix;
        },
        onComplete: function () {
          var pill = el.closest('.stat-pill');
          if (!pill) return;
          pill.classList.add('pill-pop');
          setTimeout(function () { pill.classList.remove('pill-pop'); }, 350);
        }
      });
    });
  }

  global.initMaverickCounters = initMaverickCounters;
})(window);
