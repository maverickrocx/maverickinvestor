(function (global) {
  function initMaverickCandles(opts) {
    opts = opts || {};
    var canvas = document.getElementById(opts.canvasId || 'mi-bg-canvas');
    if (!canvas) return;
    var sizeToWindow = !!opts.sizeToWindow;
    var container = sizeToWindow ? null : document.querySelector(opts.containerSelector || '.hero');
    var ctx = canvas.getContext('2d');

    function resize() {
      if (sizeToWindow) {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
      } else if (container) {
        canvas.width  = container.offsetWidth;
        canvas.height = container.offsetHeight;
      }
    }
    resize();

    var candles = [];
    var globalTrend = 0;
    var trendTimer = 0;

    function updateTrend() {
      trendTimer++;
      if (trendTimer > 40 + Math.random() * 60) {
        globalTrend += (Math.random() - 0.5) * 0.6;
        globalTrend = Math.max(-0.8, Math.min(0.8, globalTrend));
        trendTimer = 0;
      }
    }

    function makeCandle(col, h) {
      var isUp  = Math.random() > (0.5 - globalTrend * 0.35);
      var bodyH = 10 + Math.random() * 38;
      var bodyY = 20 + Math.random() * (h - bodyH - 40);
      return {
        x: col * 28 + 6,
        bodyY: bodyY,
        targetBodyH: bodyH,
        bodyH: 0,
        wickTop: bodyY - 4 - Math.random() * 14,
        wickBot: bodyY + bodyH + 4 + Math.random() * 14,
        isUp: isUp,
        alpha: 0,
        targetAlpha: 0.55 + Math.random() * 0.45,
        speed: 0.012 + Math.random() * 0.018,
        delay: Math.random() * 120,
        timer: 0,
        formTimer: 0,
        formDuration: 12 + Math.random() * 10
      };
    }

    var cols = Math.ceil(canvas.width / 28) || 1;
    for (var i = 0; i < cols; i++) candles.push(makeCandle(i, canvas.height));

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      updateTrend();
      candles.forEach(function (c, idx) {
        c.timer++;
        if (c.timer < c.delay) return;
        if (c.alpha < c.targetAlpha) c.alpha = Math.min(c.targetAlpha, c.alpha + c.speed);
        if (c.bodyH < c.targetBodyH) {
          c.formTimer++;
          c.bodyH = Math.min(c.targetBodyH, (c.formTimer / c.formDuration) * c.targetBodyH);
        }
        var color = c.isUp ? 'rgba(74,222,128,' + c.alpha + ')' : 'rgba(248,113,113,' + c.alpha + ')';
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.moveTo(c.x + 5, c.wickTop);
        ctx.lineTo(c.x + 5, c.wickBot);
        ctx.stroke();
        ctx.fillStyle = color;
        ctx.fillRect(c.x, c.bodyY, 10, c.bodyH);

        c.bodyY -= 0.12;
        c.wickTop -= 0.12;
        c.wickBot -= 0.12;
        if (c.bodyY + c.targetBodyH < -20) {
          var nc = makeCandle(idx, canvas.height);
          nc.bodyY = canvas.height + 10;
          nc.wickTop = nc.bodyY - 4 - Math.random() * 14;
          nc.wickBot = nc.bodyY + nc.targetBodyH + 4 + Math.random() * 14;
          nc.alpha = nc.targetAlpha;
          nc.bodyH = 0;
          nc.formTimer = 0;
          nc.delay = 0;
          candles[idx] = nc;
        }
      });
      requestAnimationFrame(draw);
    }
    draw();

    window.addEventListener('resize', resize);
  }

  global.initMaverickCandles = initMaverickCandles;
})(window);
