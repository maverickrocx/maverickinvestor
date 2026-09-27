// assets/js/backdrop.js — the page-wide candlestick backdrop, on every page.
// Needs assets/candles.js (load both with defer, candles.js first) and a
// <canvas id="page-candles" class="page-candles"> at the top of <body>.
// Tiles have solid backgrounds, so the candles show only in the gaps.
(function () {
  function start() {
    if (!window.initMaverickCandles || !document.getElementById('page-candles')) return;
    initMaverickCandles({
      canvasId: 'page-candles', sizeToWindow: true,
      // Deeper greens/reds on the light canvas; the originals read well on dark.
      palette: function () {
        return document.documentElement.getAttribute('data-theme') === 'dark'
          ? { up: '74,222,128', down: '248,113,113' }
          : { up: '21,128,61', down: '185,28,28' };
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
