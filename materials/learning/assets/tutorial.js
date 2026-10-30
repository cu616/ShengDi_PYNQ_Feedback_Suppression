/* 声堤 · 离线教程的四个演示
   纯原生 JS，无依赖、无网络、无音频。所有动画都在本页计算。
   约定：canvas 一律固定坐标轴，不做自动缩放（自动缩放会让任何曲线都像“被压住了”）。 */

(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  function fmt(x, d) {
    if (!isFinite(x)) return '∞';
    return x.toFixed(d === undefined ? 2 : d);
  }
  function clamp(x, a, b) { return x < a ? a : (x > b ? b : x); }

  /* ---------------- canvas 基础 ---------------- */
  function prepare(cv) {
    var dpr = window.devicePixelRatio || 1;
    var w = cv.clientWidth || cv.parentNode.clientWidth || 900;
    var h = parseInt(cv.getAttribute('height'), 10) || 240;
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    cv.style.height = h + 'px';
    var ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return { ctx: ctx, w: w, h: h };
  }

  var INK = '#16181d', MUT = '#68717e', LINE = '#dfe3e9', ACC = '#1f5f7a', BAD = '#a32323', OK = '#15663a';

  /* =========================================================================
     演示 1 · 反馈环路
     ========================================================================= */
  (function loopDemo() {
    var host = $('#d-loop');
    if (!host) return;
    var FS = 48828.125;
    var WIN_MS = 300;
    var D = 186;                       // 环路延迟（帧）：2 帧调度 + 184 帧声学
    var CAP = 1.0;                     // 满幅，超过就当作贴轨

    var el = {
      h: $('#lp-h'), g: $('#lp-g'), p: $('#lp-p'), eps: $('#lp-eps'),
      dphi: $('#lp-dphi'), cancel: $('#lp-cancel'),
      ho: $('#lp-h-o'), go: $('#lp-g-o'), po: $('#lp-p-o'), epso: $('#lp-eps-o'),
      dphio: $('#lp-dphi-o'), canc: $('#lp-cancel-o'),
      plot: $('#lp-plot'), loop: $('#lp-loop'), ratio: $('#lp-ratio'),
      level: $('#lp-level'), state: $('#lp-state'), verdict: $('#lp-verdict')
    };
    if (!el.plot) return;

    var N = Math.round(WIN_MS / 1000 * FS);
    var buf = new Float32Array(N);
    var revealed = 0;
    var raf = null;
    var paused = false;

    function params() {
      var hdB = parseFloat(el.h.value);
      var gdB = parseFloat(el.g.value);
      var phi = parseFloat(el.p.value) * Math.PI / 180;
      var eps = parseFloat(el.eps.value) / 100;   // 100% = 模型幅度与 H 相同
      var dphi = parseFloat(el.dphi.value) * Math.PI / 180;
      var on = parseFloat(el.cancel.value) > 0.5;

      var g = Math.pow(10, gdB / 20);
      var A = Math.pow(10, hdB / 20);
      var H = { re: A * Math.cos(phi), im: A * Math.sin(phi) };
      var Hh = on ? {
        re: A * eps * Math.cos(phi + dphi),
        im: A * eps * Math.sin(phi + dphi)
      } : { re: 0, im: 0 };

      // 误差通路 E = H − Ĥ
      var E = { re: H.re - Hh.re, im: H.im - Hh.im };
      // 环路系数 c = g·E
      var c = { re: g * E.re, im: g * E.im };
      return { hdB: hdB, gdB: gdB, phi: phi, eps: eps, dphi: dphi, on: on,
               g: g, A: A, H: H, Hh: Hh, E: E, c: c };
    }

    function simulate(P) {
      // u[n] = s + g·(H−Ĥ)·u[n−D]，用复数基带，s 为恒定幅度激励
      var s = 0.05;                       // −26 dBFS 的稳态激励
      var ur = new Float64Array(N + 1), ui = new Float64Array(N + 1);
      var cr = P.c.re, ci = P.c.im;
      for (var n = 0; n < N; n++) {
        var ar = 0, ai = 0;
        if (n >= D) { ar = ur[n - D]; ai = ui[n - D]; }
        var xr = s + (cr * ar - ci * ai);
        var xi = (cr * ai + ci * ar);
        // 贴轨：超过满幅就夹住，模拟真实的钳位
        var mag = Math.sqrt(xr * xr + xi * xi);
        if (mag > CAP) { xr = xr / mag * CAP; xi = xi / mag * CAP; }
        ur[n + 1] = xr; ui[n + 1] = xi;
        var m = Math.sqrt(xr * xr + xi * xi);
        buf[n] = m > 1e-9 ? 20 * Math.log10(m) : -120;
      }
      return buf;
    }

    function draw(P, done) {
      var g = prepare(el.plot);
      var ctx = g.ctx, w = g.w, h = g.h;
      var padL = 46, padR = 12, padT = 12, padB = 26;
      var pw = w - padL - padR, ph = h - padT - padB;

      var yMin = -60, yMax = 6;
      function X(i) { return padL + pw * (i / (N - 1)); }
      function Y(db) { return padT + ph * (1 - (clamp(db, yMin, yMax) - yMin) / (yMax - yMin)); }

      // 网格
      ctx.strokeStyle = LINE; ctx.lineWidth = 1; ctx.fillStyle = MUT;
      ctx.font = '11px system-ui, sans-serif'; ctx.textAlign = 'right';
      for (var d = -60; d <= 0; d += 20) {
        var y = Y(d);
        ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
        ctx.fillText(d + '', padL - 6, y + 4);
      }
      for (var ms = 0; ms <= WIN_MS; ms += 50) {
        var xx = padL + pw * (ms / WIN_MS);
        ctx.beginPath(); ctx.moveTo(xx, padT); ctx.lineTo(xx, padT + ph); ctx.stroke();
        // 首尾刻度改成左/右对齐，否则居中会超出画布被裁掉
        ctx.textAlign = ms === 0 ? 'left' : (ms === WIN_MS ? 'right' : 'center');
        ctx.fillText(ms + ' ms', xx, h - 8);
      }
      ctx.textAlign = 'center';

      // 满幅线
      ctx.strokeStyle = '#b9c0c9'; ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(padL, Y(0)); ctx.lineTo(w - padR, Y(0)); ctx.stroke();
      ctx.setLineDash([]);

      // 曲线（每个像素取桶内最大值）
      var nRev = Math.min(N, revealed);
      var unstable = Math.abs(P.c.re) > 0 || Math.abs(P.c.im) > 0;
      ctx.strokeStyle = ACC; ctx.lineWidth = 2; ctx.beginPath();
      var started = false;
      var perPx = Math.max(1, Math.ceil(nRev / pw));
      for (var i = 0; i < nRev; i += perPx) {
        var mx = -120;
        for (var j = i; j < Math.min(i + perPx, nRev); j++) if (buf[j] > mx) mx = buf[j];
        var px = X(i), py = Y(mx);
        if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
      }
      ctx.stroke();

      // 末点
      if (nRev > 0) {
        var lastDb = buf[nRev - 1];
        ctx.fillStyle = lastDb >= -0.05 ? BAD : ACC;
        ctx.beginPath(); ctx.arc(X(nRev - 1), Y(lastDb), 3, 0, 6.2832); ctx.fill();
      }
      void unstable;
    }

    function readouts(P) {
      var cAbs = Math.sqrt(P.c.re * P.c.re + P.c.im * P.c.im);
      el.loop.textContent = (cAbs > 1e-6 ? 20 * Math.log10(cAbs) : -999).toFixed(2) + ' dB';
      el.loop.className = 'v ' + (cAbs >= 1 ? 'bad' : (cAbs > 0.7 ? 'warn' : 'ok'));

      // played/source = 1/|1 − c|
      var dr = 1 - P.c.re, di = -P.c.im;
      var den = Math.sqrt(dr * dr + di * di);
      var ratioDb = den > 1e-9 ? -20 * Math.log10(den) : Infinity;
      el.ratio.textContent = (isFinite(ratioDb) ? (ratioDb >= 0 ? '+' : '') + ratioDb.toFixed(2) : '∞') + ' dB';
      el.ratio.className = 'v';

      var last = buf[N - 1];
      el.level.textContent = last.toFixed(1) + ' dBFS';
      el.level.className = 'v ' + (last > -0.1 ? 'bad' : '');

      if (cAbs >= 1) {
        el.state.textContent = '自激';
        el.state.className = 'v bad';
        el.verdict.className = 'verdict bad';
        el.verdict.textContent = '环路增益 ' + (20 * Math.log10(cAbs)).toFixed(2) +
          ' dB ≥ 0：每一圈都比上一圈大，输出顶到满幅并停在那里。这就是啸叫。';
      } else if (cAbs > 0.9) {
        el.state.textContent = '临界附近';
        el.state.className = 'v warn';
        el.verdict.className = 'verdict warn';
        el.verdict.textContent = '环路增益 ' + (20 * Math.log10(cAbs)).toFixed(2) +
          ' dB：离自激不到 1 dB。这里任何小的通路变化（人走动、开窗）都可能把它推过 1。';
      } else {
        el.state.textContent = '稳定';
        el.state.className = 'v ok';
        el.verdict.className = 'verdict ok';
        el.verdict.textContent = '环路增益 ' + (20 * Math.log10(cAbs)).toFixed(2) +
          ' dB：每一圈都在衰减，最终稳定在 ' + (isFinite(ratioDb) ? ratioDb.toFixed(2) : '∞') + ' dB 的放大量。';
      }
    }

    function recompute(animate) {
      var P = params();
      el.ho.textContent = fmt(P.hdB, 1) + ' dB';
      el.go.textContent = fmt(P.gdB, 1) + ' dB';
      el.po.textContent = fmt(parseFloat(el.p.value), 0) + '°';
      el.epso.textContent = fmt(parseFloat(el.eps.value), 0) + '%';
      el.dphio.textContent = fmt(parseFloat(el.dphi.value), 0) + '°';
      el.canc.textContent = P.on ? '开（有模型）' : '关（无模型）';

      simulate(P);
      readouts(P);
      if (animate) {
        revealed = 0;
        start();
      } else {
        revealed = N;
        draw(P, true);
      }
    }

    function tick() {
      raf = null;
      if (paused) return;
      revealed += Math.max(8, Math.round(N / 110));
      if (revealed >= N) { revealed = N; draw(params(), true); return; }
      draw(params(), false);
      raf = requestAnimationFrame(tick);
    }
    var revealTimer = null;
    function start() {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
      // 兜底：视口外/后台标签页里 rAF 会被节流，几秒后强制画完，避免停在半张图
      if (revealTimer) clearTimeout(revealTimer);
      revealTimer = setTimeout(function () {
        if (revealed < N) { revealed = N; draw(params(), true); }
      }, 1900);
    }

    $$('input', host).forEach(function (inp) {
      inp.addEventListener('input', function () { recompute(true); });
    });

    $$('button[data-lp]', host).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var k = btn.getAttribute('data-lp');
        if (k === 'pause') {
          paused = !paused;
          btn.setAttribute('aria-pressed', paused ? 'true' : 'false');
          btn.textContent = paused ? '继续' : '暂停 / 继续';
          if (!paused) start();
          return;
        }
        if (k === 'reset') { setPreset('default'); return; }
        if (k === 'preset-zero') { setPreset('zero'); return; }
        if (k === 'preset-cand') { setPreset('cand'); return; }
        if (k === 'preset-0db') { setPreset('0db'); return; }
      });
    });

    function setPreset(which) {
      var s = {
        // |H| = +4.40 dB @ 321.9 Hz，相位由 322 Hz 三点反解为 ≈ +40°
        'default': { h: 4.4, g: -8, p: 39.8, eps: 100, dphi: 0, cancel: 0 },
        'zero': { h: 4.4, g: -8, p: 39.8, eps: 100, dphi: 0, cancel: 0 },
        // 候选模型：由"CD = 6.37 dB"与"cancel 臂 played/source ≈ 0"两条实测反算出的等效模型
        // （|H−Ĥ| = 0.797、∠(H−Ĥ) ≈ 81° → eps 71 %、dphi −26°）。不是模型文件里的参数。
        'cand': { h: 4.4, g: -8, p: 39.8, eps: 71, dphi: -26.3, cancel: 1 },
        '0db': { h: 4.4, g: 0, p: 39.8, eps: 100, dphi: 0, cancel: 0 }
      }[which] || { h: 4.4, g: -8, p: 39.8, eps: 100, dphi: 0, cancel: 0 };
      el.h.value = s.h; el.g.value = s.g; el.p.value = s.p;
      el.eps.value = s.eps; el.dphi.value = s.dphi; el.cancel.value = s.cancel;
      paused = false;
      recompute(true);
    }

    window.addEventListener('resize', function () { if (revealed >= N) draw(params(), true); });

    // 暴露重置
    host._reset = function () { setPreset('default'); };
    recompute(true);
  })();

  /* =========================================================================
     演示 2 · FIR 逐抽头
     ========================================================================= */
  (function firDemo() {
    var host = $('#d-fir');
    if (!host) return;

    var H = [0.5, -0.25, 0.125];
    var el = {
      u1: $('#fir-u1'), u2: $('#fir-u2'), u3: $('#fir-u3'), m: $('#fir-m'),
      u1o: $('#fir-u1-o'), u2o: $('#fir-u2-o'), u3o: $('#fir-u3-o'), mo: $('#fir-m-o'),
      tbody: $('#fir-table tbody'), p: $('#fir-p'), w: $('#fir-w'),
      step: $('#fir-step'), verdict: $('#fir-verdict'), budget: $('#fir-budget')
    };
    if (!el.tbody) return;

    var step = 0;          // 0..3，3 表示算完
    var timer = null;

    function samples() {
      return [parseFloat(el.u1.value), parseFloat(el.u2.value), parseFloat(el.u3.value)];
    }

    function render() {
      var u = samples();
      var acc = 0, rows = '';
      for (var k = 0; k < 3; k++) {
        var done = step > k;
        var prod = done ? H[k] * u[k] : null;
        if (done) acc += prod;
        var accNow = acc;
        rows += '<tr>' +
          '<td>' + k + '</td>' +
          '<td class="num">' + (H[k] >= 0 ? '+' : '') + H[k].toFixed(3) + '</td>' +
          '<td class="num">' + (u[k] >= 0 ? '+' : '') + u[k].toFixed(2) + '</td>' +
          '<td class="num">' + (done ? '<b>' + (prod >= 0 ? '+' : '') + prod.toFixed(3) + '</b>' : '·') + '</td>' +
          '<td class="num">' + (done ? (accNow >= 0 ? '+' : '') + accNow.toFixed(3) : '—') + '</td>' +
          '<td>' + (done ? '已累加' : (k === step ? '← 下一个' : '待算')) + '</td>' +
          '</tr>';
      }
      el.tbody.innerHTML = rows;

      if (step >= 3) {
        var p = acc;
        var m = parseFloat(el.m.value);
        var w = m - p;
        el.p.textContent = (p >= 0 ? '+' : '') + p.toFixed(3);
        el.w.textContent = (w >= 0 ? '+' : '') + w.toFixed(3);
        el.w.className = 'v ' + (Math.abs(w) > 1 ? 'bad' : 'ok');
        el.step.textContent = '3 / 3（完成）';
        el.verdict.className = 'verdict ok';
        el.verdict.textContent = '预测 p = ' + p.toFixed(3) + '，残差 w = m − p = ' + w.toFixed(3) +
          '。麦克风里的 ' + p.toFixed(3) + ' 被判定为“自己放出去绕回来的”，减掉后剩下的才是新东西。';
      } else {
        el.p.textContent = '—';
        el.w.textContent = '—';
        el.w.className = 'v';
        el.step.textContent = step + ' / 3';
        el.verdict.className = 'verdict';
        el.verdict.textContent = step === 0
          ? '按“单步”开始，看累加器怎么一格一格长起来。'
          : '已累加 ' + step + ' 个抽头，累加器 = ' + (acc >= 0 ? '+' : '') + acc.toFixed(3) + '。';
      }
    }

    $$('input', host).forEach(function (inp) {
      inp.addEventListener('input', function () {
        el.u1o.textContent = (+parseFloat(el.u1.value)).toFixed(2);
        el.u2o.textContent = (+parseFloat(el.u2.value)).toFixed(2);
        el.u3o.textContent = (+parseFloat(el.u3.value)).toFixed(2);
        el.mo.textContent = (+parseFloat(el.m.value)).toFixed(2);
        render();
      });
    });

    $$('button[data-fir]', host).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var k = btn.getAttribute('data-fir');
        if (k === 'step') {
          if (timer) { clearInterval(timer); timer = null; }
          step = step >= 3 ? 0 : step + 1;
          render();
        } else if (k === 'auto') {
          if (timer) { clearInterval(timer); timer = null; btn.textContent = '自动播放'; return; }
          btn.textContent = '停止';
          if (step >= 3) { step = 0; render(); }
          timer = setInterval(function () {
            if (step >= 3) { clearInterval(timer); timer = null; btn.textContent = '自动播放'; return; }
            step++;
            render();
          }, 700);
        } else if (k === 'reset') {
          if (timer) { clearInterval(timer); timer = null; }
          step = 0;
          el.u1.value = 0.8; el.u2.value = -0.4; el.u3.value = 0.2; el.m.value = 0.6;
          el.u1o.textContent = '0.80'; el.u2o.textContent = '-0.40';
          el.u3o.textContent = '0.20'; el.mo.textContent = '0.60';
          render();
        }
      });
    });

    /* 预算条 */
    function drawBudget() {
      var cv = el.budget;
      if (!cv) return;
      var g = prepare(cv), ctx = g.ctx, w = g.w, h = g.h;
      var padL = 8, padR = 8, y = 34, bh = 34;
      var pw = w - padL - padR;
      var TOTAL = 2048, FIRC = 1539;

      ctx.font = '12px system-ui, sans-serif';
      ctx.textAlign = 'left'; ctx.fillStyle = MUT;
      ctx.fillText('一帧 = 2048 拍（20.48 µs）', padL, 18);

      ctx.fillStyle = '#e6ebf1';
      ctx.fillRect(padL, y, pw, bh);

      var wF = pw * FIRC / TOTAL;
      ctx.fillStyle = '#1f5f7a';
      ctx.fillRect(padL, y, wF, bh);
      ctx.fillStyle = '#c8d8e3';
      ctx.fillRect(padL + wF, y, pw - wF, bh);

      ctx.fillStyle = '#fff'; ctx.textAlign = 'center';
      ctx.font = '600 12px system-ui, sans-serif';
      ctx.fillText('FIR 1539 拍', padL + wF / 2, y + 22);

      ctx.fillStyle = '#3d4653';
      ctx.fillText('其余 509', padL + wF + (pw - wF) / 2, y + 22);

      // 刻度：0 / 2048 一行，681 的标注单独一行，避免和右端刻度挤在一起被裁
      ctx.fillStyle = MUT; ctx.font = '11px system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText('0', padL, y + bh + 18);
      ctx.textAlign = 'right';
      ctx.fillText('2048', w - padR, y + bh + 18);

      var x681 = padL + pw * (3 * 681 + 3) / TOTAL;
      ctx.strokeStyle = '#a32323'; ctx.lineWidth = 1.5; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x681, y - 6); ctx.lineTo(x681, y + bh + 6); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#a32323'; ctx.font = '11px system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText('681 抽头 = 2046 拍（每帧算得完的上限）', w - padR, y + bh + 38);
      ctx.textAlign = 'left';
    }

    window.addEventListener('resize', drawBudget);

    el.u1o.textContent = '0.80'; el.u2o.textContent = '-0.40';
    el.u3o.textContent = '0.20'; el.mo.textContent = '0.60';
    render();
    drawBudget();
    host._reset = function () {
      if (timer) { clearInterval(timer); timer = null; }
      step = 0;
      el.u1.value = 0.8; el.u2.value = -0.4; el.u3.value = 0.2; el.m.value = 0.6;
      el.u1o.textContent = '0.80'; el.u2o.textContent = '-0.40';
      el.u3o.textContent = '0.20'; el.mo.textContent = '0.60';
      render();
    };
  })();

  /* =========================================================================
     演示 3 · 宽残差：先钳 vs 后钳（真实定点整数）
     ========================================================================= */
  (function wideDemo() {
    var host = $('#d-wide');
    if (!host) return;

    var SCALE = 8388608;         // 2^23
    var MAX24 = 8388607;         // +满幅
    var MIN24 = -8388608;        // −满幅

    var el = {
      m: $('#wr-m'), p: $('#wr-p'), sign: $('#wr-sign'), g: $('#wr-g'),
      mo: $('#wr-m-o'), po: $('#wr-p-o'), so: $('#wr-sign-o'), go: $('#wr-g-o'),
      rows: $('#wr-rows'), v2: $('#wr-v2'), v3: $('#wr-v3'),
      stop: $('#wr-stop'), head: $('#wr-head'), verdict: $('#wr-verdict')
    };
    if (!el.rows) return;

    function clamp24(x) { return x > MAX24 ? MAX24 : (x < MIN24 ? MIN24 : x); }
    function over24(x) { return x > MAX24 || x < MIN24; }

    // 与 RTL 一致：半值远离零
    function roundShift(x, bits) {
      var sign = x < 0 ? -1 : 1;
      var mag = Math.abs(x);
      var half = Math.pow(2, bits - 1);
      return sign * Math.floor((mag + half) / Math.pow(2, bits));
    }

    function compute() {
      var mDb = parseFloat(el.m.value);
      var pMagDb = parseFloat(el.p.value);
      var neg = parseFloat(el.sign.value) > 0.5;
      var gDb = parseFloat(el.g.value);

      var M = clamp24(Math.round(Math.pow(10, mDb / 20) * SCALE));
      var Pmag = Math.min(MAX24, Math.round(Math.pow(10, pMagDb / 20) * SCALE));
      var P = neg ? -Pmag : Pmag;

      var W = M - P;                              // 25 位宽残差
      var g12 = Math.round(4096 * Math.pow(10, gDb / 20));

      // v2：先钳到 24 位，再乘增益
      var Ev2 = clamp24(W);
      var prod2 = roundShift(g12 * Ev2, 12);
      var out2 = clamp24(prod2);

      // v3：保留 25 位过增益，最后钳一次
      var prod3 = roundShift(g12 * W, 12);
      var out3 = clamp24(prod3);

      return {
        mDb: mDb, pDb: pMagDb, neg: neg, gDb: gDb, g12: g12,
        M: M, P: P, W: W, Ev2: Ev2, prod2: prod2, out2: out2,
        prod3: prod3, out3: out3,
        wOver: over24(W), ev2Over: over24(W), prod2Over: over24(prod2),
        prod3Over: over24(prod3)
      };
    }

    function cell(v, isOver, suffix) {
      var s = (v / SCALE);
      return '<td class="num">' + (v >= 0 ? '+' : '') + v + '　<span style="color:#68717e">' +
        (s >= 0 ? '' : '') + s.toFixed(4) + '×</span>' + (suffix || '') + '</td>' +
        '<td>' + (isOver ? '<b style="color:#a32323">越界</b>' : '<span style="color:#15663a">在范围内</span>') + '</td>';
    }

    function render() {
      var r = compute();
      el.mo.textContent = fmt(r.mDb, 1) + ' dBFS';
      el.po.textContent = (r.neg ? '−' : '+') + fmt(r.pDb, 1) + ' dBFS';
      el.so.textContent = r.neg ? '负（与麦克风反相）' : '正（同相）';
      el.go.textContent = fmt(r.gDb, 1) + ' dB';

      var rows = '';
      rows += '<tr><td>麦克风 <i>m</i>（24 位）</td>' + cell(r.M, false) + '</tr>';
      rows += '<tr><td>预测 <i>p</i>（24 位）</td>' + cell(r.P, false) + '</tr>';
      rows += '<tr><td><b>宽残差 <i>w</i> = m − p（25 位）</b></td>' + cell(r.W, r.wOver) + '</tr>';
      rows += '<tr><td>v2：先钳 → <i>e</i></td>' + cell(r.Ev2, r.ev2Over) + '</tr>';
      rows += '<tr><td>v2：<i>e</i> × <i>g</i></td>' + cell(r.prod2, r.prod2Over) + '</tr>';
      rows += '<tr><td>v2：输出</td>' + cell(r.out2, false) + '</tr>';
      rows += '<tr><td>v3：<i>w</i> × <i>g</i>（不钳）</td>' + cell(r.prod3, r.prod3Over) + '</tr>';
      rows += '<tr><td><b>v3：输出</b></td>' + cell(r.out3, false) + '</tr>';
      el.rows.innerHTML = rows;

      var o2 = r.out2 / SCALE, o3 = r.out3 / SCALE;
      el.v2.textContent = o2.toFixed(4) + '×';
      el.v3.textContent = o3.toFixed(4) + '×';
      var head = o3 > 0 ? -20 * Math.log10(o3) : Infinity;
      el.head.textContent = isFinite(head) ? '+' + head.toFixed(1) + ' dB' : '∞';

      var stopped = r.ev2Over;
      el.stop.textContent = stopped ? '会（残差越界触发保护）' : '不会';
      el.stop.className = 'v ' + (stopped ? 'bad' : 'ok');

      var d;
      if (r.g12 === 0) {
        el.verdict.className = 'verdict';
        el.verdict.textContent = '增益为 0（Q4.12 码值 0），输出恒为 0，这一档没有意义。';
      } else if (!r.wOver) {
        el.verdict.className = 'verdict ok';
        el.verdict.textContent = '宽残差没有越界，两条路径结果相同（' + o3.toFixed(4) + '× 满幅）。' +
          '这种情况下 v2 和 v3 没有区别，差别只在越界时才出现。';
      } else if (stopped && !r.prod3Over) {
        d = 20 * Math.log10(Math.abs(o3 / o2));
        el.verdict.className = 'verdict bad';
        el.verdict.innerHTML = '宽残差 ' + (r.W / SCALE).toFixed(4) + '× 越界，但乘完 ' + fmt(r.gDb, 1) +
          ' dB 之后只有 ' + o3.toFixed(4) + '× 满幅（余量 ' + (isFinite(head) ? head.toFixed(1) : '∞') + ' dB）。' +
          'v2 会在中间就钳住并<b>停声</b>，v3 继续跑。两者输出差 ' + d.toFixed(2) + ' dB。';
        /* 上面这行含标签，改用 innerHTML 输出 */
      } else {
        el.verdict.className = 'verdict warn';
        el.verdict.innerHTML = '乘增益之后仍然越界（' + (r.prod3 / SCALE).toFixed(4) +
          '×），这时 v3 也会钳——<b>这是真的过载</b>，该保护。说明性能上限确实到了，不是误停。';
      }
    }

    function preset(which) {
      if (which === 'field') {
        el.m.value = 0; el.p.value = -32.7; el.sign.value = 1; el.g.value = -8;
      } else if (which === 'quiet') {
        el.m.value = -20; el.p.value = -30; el.sign.value = 1; el.g.value = -8;
      } else if (which === 'huge') {
        el.m.value = 0; el.p.value = 0; el.sign.value = 1; el.g.value = 0;
      } else {
        el.m.value = -0.01; el.p.value = -32.7; el.sign.value = 1; el.g.value = -8;
      }
      render();
    }

    $$('input', host).forEach(function (inp) { inp.addEventListener('input', render); });
    $$('button[data-wr]', host).forEach(function (btn) {
      btn.addEventListener('click', function () { preset(btn.getAttribute('data-wr')); });
    });

    host._reset = function () { preset('reset'); };
    render();
  })();

  /* =========================================================================
     演示 4 · 捕获窗口：含源还是只取停源尾段
     ========================================================================= */
  (function windowDemo() {
    var host = $('#d-window');
    if (!host) return;

    var NF = 16384, SRC = 15407;
    var el = {
      plot: $('#wd-plot'), start: $('#wd-start'), len: $('#wd-len'),
      starto: $('#wd-start-o'), leno: $('#wd-len-o'),
      rows: $('#wd-rows'), verdict: $('#wd-verdict')
    };
    if (!el.plot) return;

    // 固定种子，保证每次打开数字一致
    var seed = 12345;
    function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }

    // 合成：有源段 mic 大、残差小（抵消 10 dB）；尾段只剩底噪，残差底噪反而更高（抵消为负）
    var mic = new Float32Array(NF), res = new Float32Array(NF);
    var active = new Uint8Array(NF);
    for (var i = 0; i < NF; i++) {
      var isSrc = i < SRC;
      active[i] = isSrc ? 1 : 0;
      if (isSrc) {
        mic[i] = 0.050 * (0.55 + 0.45 * rnd());
        res[i] = mic[i] * Math.pow(10, -10 / 20) * (0.8 + 0.4 * rnd());
      } else {
        mic[i] = 0.00070 * (0.5 + rnd());
        res[i] = 0.00110 * (0.5 + rnd());
      }
    }

    function stats(a, b) {
      var n = b - a, sm = 0, sr = 0, act = 0;
      for (var i = a; i < b; i++) { sm += mic[i] * mic[i]; sr += res[i] * res[i]; act += active[i]; }
      var rmsM = Math.sqrt(sm / n), rmsR = Math.sqrt(sr / n);
      return {
        n: n,
        act: act / n,
        mic: 20 * Math.log10(rmsM),
        res: 20 * Math.log10(rmsR),
        sup: 20 * Math.log10(rmsM / rmsR)
      };
    }

    function draw(a, b) {
      var g = prepare(el.plot), ctx = g.ctx, w = g.w, h = g.h;
      var padL = 10, padR = 10, padT = 22, bh = 46;
      var pw = w - padL - padR;

      ctx.font = '12px system-ui, sans-serif';
      ctx.fillStyle = MUT; ctx.textAlign = 'left';
      ctx.fillText('捕获缓冲 16384 帧（335.5 ms）', padL, 14);

      // 有源 / 尾段
      var xSrc = padL + pw * (SRC / NF);
      ctx.fillStyle = '#dceaf2';
      ctx.fillRect(padL, padT, xSrc - padL, bh);
      ctx.fillStyle = '#f0f1f3';
      ctx.fillRect(xSrc, padT, padL + pw - xSrc, bh);

      ctx.fillStyle = '#1f5f7a'; ctx.textAlign = 'center';
      ctx.fillText('源在放（15407 帧）', padL + (xSrc - padL) / 2, padT + bh / 2 + 4);
      var tailW = padL + pw - xSrc;
      ctx.fillStyle = '#68717e';
      if (tailW > 96) {
        ctx.fillText('源已停', xSrc + tailW / 2, padT + bh / 2 + 4);
      } else {
        ctx.textAlign = 'right';
        ctx.fillText('源已停 →', padL + pw, padT + bh + 16);
        ctx.textAlign = 'center';
      }

      // 波形（对数幅度）
      ctx.beginPath(); ctx.strokeStyle = '#1f5f7a'; ctx.lineWidth = 1;
      for (var i = 0; i < NF; i += 4) {
        var db = 20 * Math.log10(mic[i] + 1e-9);
        var y = padT + bh - clamp((db + 80) / 80, 0, 1) * bh;
        var x = padL + pw * (i / NF);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // 选择窗
      var x1 = padL + pw * (a / NF), x2 = padL + pw * (b / NF);
      ctx.fillStyle = 'rgba(31,95,122,.18)';
      ctx.fillRect(x1, padT, x2 - x1, bh);
      ctx.strokeStyle = '#a32323'; ctx.lineWidth = 2;
      ctx.strokeRect(x1, padT, Math.max(1, x2 - x1), bh);

      ctx.fillStyle = '#a32323'; ctx.textAlign = 'center'; ctx.font = '11px system-ui, sans-serif';
      ctx.fillText('统计窗口', (x1 + x2) / 2, padT - 6);
    }

    function render() {
      var a = parseInt(el.start.value, 10);
      var L = parseInt(el.len.value, 10);
      var b = Math.min(NF, a + L);
      el.starto.textContent = a + '';
      el.leno.textContent = L + '（' + (1000 * L / 48828.125).toFixed(0) + ' ms）';

      var s = stats(a, b);
      el.rows.innerHTML =
        '<tr><td>窗口帧数</td><td class="num">' + s.n + '</td></tr>' +
        '<tr><td>其中有源帧占比</td><td class="num">' + (100 * s.act).toFixed(1) + ' %</td></tr>' +
        '<tr><td>麦克风 RMS</td><td class="num">' + s.mic.toFixed(2) + ' dBFS</td></tr>' +
        '<tr><td>残差 RMS</td><td class="num">' + s.res.toFixed(2) + ' dBFS</td></tr>' +
        '<tr><td><b>看起来的“抑制”</b></td><td class="num"><b>' + s.sup.toFixed(2) + ' dB</b></td></tr>';

      if (s.act < 0.5) {
        el.verdict.className = 'verdict bad';
        el.verdict.innerHTML = '窗口里只有 ' + (100 * s.act).toFixed(1) +
          '% 是有源帧：这一段的“抑制”是底噪之比，不是抵消效果。<b>判无效。</b>';
      } else if (s.act < 0.98) {
        el.verdict.className = 'verdict warn';
        el.verdict.textContent = '窗口混进了停源尾段（无源 ' + (100 - 100 * s.act).toFixed(1) +
          '%）。数字还接近，但口径已经不纯——写报告时要说清窗内是否含静音。';
      } else {
        el.verdict.className = 'verdict ok';
        el.verdict.textContent = '窗口全在有源段内，读数可用。' +
          '这也是为什么脚本要逐段判断“源是否已停”，而不是按帧号硬切。';
      }
      draw(a, b);
    }

    function setWin(name) {
      if (name === 'all') { el.start.value = 0; el.len.value = NF; }
      else if (name === 'src') { el.start.value = 0; el.len.value = SRC; }
      else if (name === 'tail') { el.start.value = SRC; el.len.value = NF - SRC; }
      else if (name === 'mid') { el.start.value = 6000; el.len.value = 4096; }
      render();
    }

    $$('input', host).forEach(function (inp) { inp.addEventListener('input', render); });
    $$('button[data-wd]', host).forEach(function (btn) {
      btn.addEventListener('click', function () { setWin(btn.getAttribute('data-wd')); });
    });

    host._reset = function () { setWin('src'); };
    setWin('src');
  })();

  /* =========================================================================
     全局：导航高亮、回到顶部、概览模式
     ========================================================================= */
  (function globalBits() {
    var links = $$('.rail a[href^="#"]').filter(function (a) {
      return a.getAttribute('href').length > 1;
    });
    var secs = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); })
      .filter(Boolean);

    if ('IntersectionObserver' in window && secs.length) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (!e.isIntersecting) return;
          links.forEach(function (a) {
            a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id);
          });
        });
      }, { rootMargin: '-10% 0px -80% 0px', threshold: 0 });
      secs.forEach(function (s) { io.observe(s); });
    }

    var top = $('#totop');
    if (top) {
      window.addEventListener('scroll', function () {
        top.classList.toggle('on', window.scrollY > 600);
      }, { passive: true });
      top.addEventListener('click', function () {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }

    // 概览 / 深入
    var banner = null;
    function quickMode(on) {
      document.body.classList.toggle('quick', on);
      if (!banner) {
        banner = document.createElement('div');
        banner.className = 'callout';
        banner.id = 'quick-banner';
        banner.style.position = 'sticky';
        banner.style.top = '0';
        banner.style.zIndex = '30';
        banner.style.margin = '0';
        banner.style.borderRadius = '0';
        banner.style.fontSize = '14px';
        var main = document.querySelector('main');
        main.insertBefore(banner, main.firstChild);
      }
      if (on) {
        var n = $$('.card.failure').length + $$('.qa').length;
        banner.innerHTML = '<b>概览模式</b>：已隐藏 ' + n +
          ' 处失败案例与问答细节，只保留主线。<a href="#" id="qb-off">恢复全部内容</a>';
        banner.style.display = '';
        var off = $('#qb-off');
        if (off) off.addEventListener('click', function (e) {
          e.preventDefault(); quickMode(false); document.getElementById('s0').scrollIntoView();
        });
      } else {
        banner.style.display = 'none';
      }
    }
    $$('.entry a').forEach(function (a) {
      a.addEventListener('click', function (e) {
        var m = a.getAttribute('data-mode');
        if (!m) return;
        e.preventDefault();
        quickMode(m === 'quick');
        var t = document.getElementById(m === 'quick' ? 's0' : 's1');
        if (t) t.scrollIntoView();
      });
    });

    // 重置全部
    var ra = $('#reset-all');
    if (ra) {
      ra.addEventListener('click', function (e) {
        e.preventDefault();
        ['#d-loop', '#d-fir', '#d-wide', '#d-window'].forEach(function (sel) {
          var h = document.querySelector(sel);
          if (h && h._reset) h._reset();
        });
      });
    }
  })();

})();
