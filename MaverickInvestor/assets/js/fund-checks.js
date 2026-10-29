// assets/js/fund-checks.js — Tools page: "Hidden duplicate check" and
// "Crash replay". Both read same-origin files written each morning by
// tools/build_nav_data.py: data/fund-list.json, data/nav-history/<code>.json
// and data/crash-replay.json.
(function () {
  var LIST = null;
  var GROUP_ORDER = ['Large Cap', 'Flexi Cap', 'Mid Cap', 'Small Cap', 'Index', 'Global & Gold', 'Gold', 'Debt', 'Other'];
  var DUP_DEFAULTS = ['118825', '119018', '120716', '122639', '125354'];
  var DUP_SLOTS = 6;

  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }
  function rupees(n) { return '₹' + Math.round(n).toLocaleString('en-IN'); }
  function monthYear(iso) {
    if (!iso) return '—';
    var p = iso.split('-');
    return new Date(+p[0], +p[1] - 1, +(p[2] || 1)).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
  }
  function getJSON(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }

  function fundOptions(selected, allowNone) {
    var groups = {};
    Object.keys(LIST).forEach(function (code) {
      var f = LIST[code];
      (groups[f.group] = groups[f.group] || []).push([code, f.name]);
    });
    var order = GROUP_ORDER.filter(function (g) { return groups[g]; })
      .concat(Object.keys(groups).filter(function (g) { return GROUP_ORDER.indexOf(g) < 0; }));
    return (allowNone ? '<option value="">— none —</option>' : '') + order.map(function (g) {
      return '<optgroup label="' + esc(g) + '">' + groups[g].sort(function (a, b) { return a[1].localeCompare(b[1]); })
        .map(function (o) { return '<option value="' + o[0] + '"' + (o[0] === selected ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</optgroup>';
    }).join('');
  }

  /* ─────────────────────────────────────────────────────────
     HIDDEN DUPLICATE CHECK
     Two measures over the last 5 years of monthly returns:
       correlation  — do they rise and fall in the same months?
       drift        — how far apart do their returns run (tracking error, % a year)?
     Near-duplicate: corr ≥ 0.95 and drift ≤ 4%. Heavy overlap: corr ≥ 0.90 and drift ≤ 6%.
  ───────────────────────────────────────────────────────── */
  var histCache = {};
  function monthlyReturns(code) {
    if (histCache[code]) return Promise.resolve(histCache[code]);
    return getJSON('data/nav-history/' + code + '.json').then(function (h) {
      var rows = h.data.slice();
      // rows[0] is the latest NAV; drop it when it falls in the same month as rows[1]
      if (rows.length > 1 && rows[0].date.slice(3) === rows[1].date.slice(3)) rows.shift();
      var byMonth = {};
      rows.forEach(function (r) { var p = r.date.split('-'); byMonth[p[2] + '-' + p[1]] = parseFloat(r.nav); });
      return (histCache[code] = byMonth);
    });
  }

  function compare(a, b) {
    var keys = Object.keys(a).filter(function (k) { return k in b; }).sort().slice(-61);
    var ra = [], rb = [];
    for (var i = 1; i < keys.length; i++) {
      ra.push(a[keys[i]] / a[keys[i - 1]] - 1);
      rb.push(b[keys[i]] / b[keys[i - 1]] - 1);
    }
    var n = ra.length;
    if (n < 24) return null;
    var ma = ra.reduce(function (s, x) { return s + x; }, 0) / n, mb = rb.reduce(function (s, x) { return s + x; }, 0) / n;
    var cov = 0, va = 0, vb = 0, dm = 0, dv = 0, d;
    for (i = 0; i < n; i++) { cov += (ra[i] - ma) * (rb[i] - mb); va += Math.pow(ra[i] - ma, 2); vb += Math.pow(rb[i] - mb, 2); }
    var diffs = ra.map(function (x, j) { return x - rb[j]; });
    dm = diffs.reduce(function (s, x) { return s + x; }, 0) / n;
    diffs.forEach(function (x) { dv += Math.pow(x - dm, 2); });
    var corr = va && vb ? cov / Math.sqrt(va * vb) : 0;
    var drift = Math.sqrt(dv / n) * Math.sqrt(12) * 100;
    var level = corr >= 0.95 && drift <= 4 ? 'dup' : (corr >= 0.90 && drift <= 6 ? 'overlap' : 'variety');
    return { corr: corr, drift: drift, months: n, level: level };
  }

  var LEVEL_TEXT = {
    dup: ['Near-duplicates', 'They rise and fall in the same months by almost the same amount. Holding both mostly means paying two expense ratios for one result.'],
    overlap: ['Heavy overlap', 'Mostly the same ride. The second fund adds a little variety, but less than its name suggests.'],
    variety: ['Adds variety', 'These behave differently enough that holding both genuinely spreads your risk.']
  };

  function runDup() {
    var picks = [];
    document.querySelectorAll('#dupPickers select').forEach(function (s) { if (s.value && picks.indexOf(s.value) < 0) picks.push(s.value); });
    var out = document.getElementById('dupResult');
    if (picks.length < 2) { out.innerHTML = '<p class="fc-empty">Pick at least two different funds.</p>'; return; }
    out.innerHTML = '<p class="fc-empty">Comparing…</p>';
    Promise.all(picks.map(monthlyReturns)).then(function (series) {
      var pairs = [], matrix = {};
      for (var i = 0; i < picks.length; i++) for (var j = i + 1; j < picks.length; j++) {
        var c = compare(series[i], series[j]);
        matrix[i + '-' + j] = matrix[j + '-' + i] = c;
        if (c) pairs.push({ a: i, b: j, c: c });
      }
      // Funds joined by a near-duplicate link count as one "behaviour"
      var parent = picks.map(function (_, k) { return k; });
      function root(k) { return parent[k] === k ? k : (parent[k] = root(parent[k])); }
      pairs.forEach(function (p) { if (p.c.level === 'dup') parent[root(p.a)] = root(p.b); });
      var distinct = picks.filter(function (_, k) { return root(k) === k; }).length;
      var rank = { dup: 0, overlap: 1, variety: 2 };
      pairs.sort(function (x, y) { return rank[x.c.level] - rank[y.c.level] || y.c.corr - x.c.corr; });
      var name = function (k) { return LIST[picks[k]].name; };

      var head = distinct < picks.length
        ? 'Your <strong>' + picks.length + ' funds</strong> behave like <strong>' + distinct + '</strong>.'
        : 'Your <strong>' + picks.length + ' funds</strong> each bring something different.';
      var cells = '<div class="dup-matrix" style="--n:' + picks.length + '"><span></span>' +
        picks.map(function (_, k) { return '<span class="dm-h">' + (k + 1) + '</span>'; }).join('') +
        picks.map(function (_, r) {
          return '<span class="dm-h dm-row" title="' + esc(name(r)) + '">' + (r + 1) + '</span>' + picks.map(function (_, k) {
            if (k === r) return '<span class="dm-c dm-self"></span>';
            var m = matrix[r + '-' + k];
            return m ? '<span class="dm-c dm-' + m.level + '" title="' + esc(name(r)) + ' vs ' + esc(name(k)) + ': correlation ' + m.corr.toFixed(2) + ', drift ' + m.drift.toFixed(1) + '% a year">' + m.corr.toFixed(2) + '</span>' : '<span class="dm-c">—</span>';
          }).join('');
        }).join('') + '</div>';
      var legend = '<ol class="dup-legend">' + picks.map(function (_, k) { return '<li>' + esc(name(k)) + '</li>'; }).join('') + '</ol>';
      var list = pairs.filter(function (p) { return p.c.level !== 'variety'; }).map(function (p) {
        var t = LEVEL_TEXT[p.c.level];
        return '<li class="dup-pair is-' + p.c.level + '"><span class="dup-badge">' + t[0] + '</span> <strong>' + esc(name(p.a)) + '</strong> &amp; <strong>' + esc(name(p.b)) + '</strong>. ' + t[1] +
          ' <span class="dup-num">Correlation ' + p.c.corr.toFixed(2) + ' · returns drift apart by about ' + p.c.drift.toFixed(1) + '% a year · last ' + p.c.months + ' months.</span></li>';
      }).join('');
      var variety = pairs.filter(function (p) { return p.c.level === 'variety'; }).length;
      out.innerHTML = '<p class="fc-headline">' + head + '</p>' +
        '<div class="dup-viz">' + cells + legend + '</div>' +
        (list ? '<ul class="dup-pairs">' + list + '</ul>' : '') +
        (variety ? '<p class="fc-note">' + variety + ' other pair' + (variety > 1 ? 's' : '') + ' add genuine variety.</p>' : '') +
        '<p class="fc-note">Correlation runs from −1 to 1: 1 means the two always move together. Drift is how far apart their yearly returns typically run. This reads return patterns, not portfolios; two funds can hold different stocks and still behave alike.</p>';
    }).catch(function () { out.innerHTML = '<p class="fc-empty">Couldn\'t load fund data just now. Please try again shortly.</p>'; });
  }

  function initDup() {
    var box = document.getElementById('dupPickers');
    var html = '';
    for (var i = 0; i < DUP_SLOTS; i++) {
      html += '<label class="fc-pick"><span>' + (i + 1) + '</span><select aria-label="Fund ' + (i + 1) + '">' + fundOptions(DUP_DEFAULTS[i] || '', true) + '</select></label>';
    }
    box.innerHTML = html;
    box.addEventListener('change', runDup);
    runDup();
  }

  /* ─────────────────────────────────────────────────────────
     CRASH REPLAY
  ───────────────────────────────────────────────────────── */
  var CRASH = null;

  function spark(fund, market) {
    var W = 260, H = 64, pad = 4;
    var all = fund.concat(market || []).concat([100]);
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    var len = Math.max(fund.length, (market || []).length);
    var x = function (i) { return pad + i / Math.max(1, len - 1) * (W - 2 * pad); };
    var y = function (v) { return H - pad - (v - lo) / Math.max(1, hi - lo) * (H - 2 * pad); };
    var line = function (arr) { return arr.map(function (v, i) { return (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1); }).join(''); };
    return '<svg class="cr-spark" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true">' +
      '<line x1="0" x2="' + W + '" y1="' + y(100).toFixed(1) + '" y2="' + y(100).toFixed(1) + '" class="cr-base"/>' +
      (market ? '<path d="' + line(market) + '" class="cr-mkt"/>' : '') +
      '<path d="' + line(fund) + '" class="cr-fund"/></svg>';
  }

  function runCrash() {
    var code = document.getElementById('crFund').value;
    var amt = +document.getElementById('crAmt').value;
    document.getElementById('crAmtLbl').textContent = rupees(amt);
    var out = document.getElementById('crResult');
    var mkt = CRASH.market;
    var rows = CRASH.crashes.slice().reverse().filter(function (c) { return c.funds[code]; });
    if (!rows.length) { out.innerHTML = '<p class="fc-empty">This fund is too new to have been through a 10%+ market fall.</p>'; return; }
    var times = rows.map(function (c) { return c.funds[code].months; }).filter(function (m) { return m != null; }).sort(function (a, b) { return a - b; });
    var worst = rows.reduce(function (w, c) { return c.funds[code].low < w.funds[code].low ? c : w; });
    var head = 'Through <strong>' + rows.length + ' market falls</strong> since ' + rows[rows.length - 1].peak.slice(0, 4) +
      ', the worst for this fund was the ' + esc(worst.name) + ': <strong>' + rupees(amt * worst.funds[code].low / 100) + '</strong> at the bottom' +
      (times.length ? '. Each time it recovered, it took between <strong>' + times[0].toFixed(0) + ' and ' + times[times.length - 1].toFixed(0) + ' months</strong> to get back to where it started.' : '.');
    out.innerHTML = '<p class="fc-headline">' + head + '</p><div class="cr-list">' + rows.map(function (c) {
      var f = c.funds[code], m = code !== mkt ? c.funds[mkt] : null;
      var back = f.back
        ? 'Back to ' + rupees(amt) + ' by <strong>' + monthYear(f.back) + '</strong>, ' + f.months.toFixed(0) + ' months after the peak.'
        : '<strong>Not back to ' + rupees(amt) + ' yet.</strong>';
      return '<article class="cr-item">' +
        '<div class="cr-top"><h4>' + esc(c.name) + '</h4><span class="cr-when">' + monthYear(c.peak) + (c.recovered ? ' – ' + monthYear(c.recovered) : ' – ongoing') + ' · Nifty 50 fell ' + Math.abs(c.depth).toFixed(0) + '%</span></div>' +
        spark(f.path, m && m.path) +
        '<p class="cr-line">' + rupees(amt) + ' invested at the peak fell to <strong class="neg">' + rupees(amt * f.low / 100) + '</strong> (' + (f.low - 100).toFixed(0) + '%) by ' + monthYear(f.lowDate) + '. ' + back + '</p>' +
        '<p class="cr-sub">Held until today: <strong>' + rupees(amt * f.today / 100) + '</strong>' +
        (m ? ' · Nifty 50 index fund: low ' + rupees(amt * m.low / 100) + (m.months != null ? ', back in ' + m.months.toFixed(0) + ' months' : ', not back yet') : '') + '</p>' +
        '</article>';
    }).join('') + '</div>' +
      '<p class="fc-note">Solid line: this fund. Dashed: Nifty 50 index fund. A "market fall" is any time the Nifty 50 dropped 10% or more from a peak. Selling at the bottom would have locked in the loss; past recoveries don\'t guarantee future ones.</p>';
  }

  function initCrash() {
    var sel = document.getElementById('crFund');
    var codes = {};
    CRASH.crashes.forEach(function (c) { Object.keys(c.funds).forEach(function (k) { codes[k] = 1; }); });
    var keep = {};
    Object.keys(LIST).forEach(function (k) { if (codes[k]) keep[k] = LIST[k]; });
    var full = LIST; LIST = keep;
    sel.innerHTML = fundOptions('118825', false);
    LIST = full;
    sel.addEventListener('change', runCrash);
    document.getElementById('crAmt').addEventListener('input', runCrash);
    runCrash();
  }

  Promise.all([getJSON('data/fund-list.json'), getJSON('data/crash-replay.json')]).then(function (r) {
    LIST = r[0]; CRASH = r[1];
    initDup();
    initCrash();
  }).catch(function () {
    ['dupResult', 'crResult'].forEach(function (id) {
      document.getElementById(id).innerHTML = '<p class="fc-empty">Couldn\'t load fund data just now. Please try again shortly.</p>';
    });
  });
})();
