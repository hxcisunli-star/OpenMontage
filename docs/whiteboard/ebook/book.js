/* 电子书平台的增强脚本：正文、图表、答案都是静态页面，不靠它。没有脚本时，仍然能读、能点链接、能展开折叠；脚本只加：视频跳转、章节高亮、阅读进度和“读过”标记、搜索、浅色深色切换。 */
(function () {
  'use strict';
  var ROOT = document.body.getAttribute('data-root') || '';
  var video = document.getElementById('lesson-video');
  var narrow = window.matchMedia ? window.matchMedia('(max-width: 1079px)') : { matches: true };
  var KEY = 'chai-chai-zhuang-zhuang';

  function store(k, v) { try { if (v === undefined) return localStorage.getItem(KEY + '.' + k); localStorage.setItem(KEY + '.' + k, v); } catch (e) { return null; } }

  /* 视频跳转 */
  function seekTo(t) {
    if (!video || !isFinite(t)) return;
    try { video.currentTime = t; var p = video.play(); if (p && p.catch) p.catch(function () {}); } catch (e) {}
    if (narrow.matches && video.scrollIntoView) video.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-seek]') : null;
    if (!el || !video) return;
    e.preventDefault();
    seekTo(parseFloat(el.getAttribute('data-seek')));
  });
  if (video) {
    var btns = Array.prototype.slice.call(document.querySelectorAll('.seek'));
    video.addEventListener('timeupdate', function () {
      var cur = -1;
      btns.forEach(function (b, i) { if (video.currentTime >= parseFloat(b.getAttribute('data-seek')) - 0.05) cur = i; });
      btns.forEach(function (b, i) { b.classList.toggle('active', i === cur); });
    });
  }

  /* 小窗视频（2026-11-18 起）：宽屏上视频在页头；页头滚出屏幕后，视频本身改成固定定位，停在右栏顶上预留的空位里。
     只切换类名、改坐标，不移动视频元素，所以播放不会中断；窄屏、没有脚本时都留在原处。 */
  var player = document.getElementById('player'), slot = document.querySelector('.pip-slot'), side = document.querySelector('.side');
  var wide = window.matchMedia ? window.matchMedia('(min-width: 1080px)') : { matches: false };
  if (player && slot && side && video && 'IntersectionObserver' in window) {
    var pipOn = false, heroVisible = true, raf = 0;
    var place = function () {
      raf = 0; decide(); if (!pipOn) return;
      var r = slot.getBoundingClientRect();
      video.style.left = r.left + 'px'; video.style.width = r.width + 'px'; video.style.top = Math.max(r.top, 12) + 'px';
    };
    var setPip = function (on) {
      if (on === pipOn) return; pipOn = on;
      player.classList.toggle('pip', on); side.classList.toggle('pip-on', on);
      if (!on) { video.style.left = video.style.width = video.style.top = ''; } else place();
    };
    var decide = function () { setPip(wide.matches && !heroVisible && player.getBoundingClientRect().bottom < 0); };
    new IntersectionObserver(function (es) { heroVisible = es[es.length - 1].isIntersecting; decide(); }).observe(player);
    window.addEventListener('scroll', function () { if (!raf) raf = requestAnimationFrame(place); }, { passive: true });      // a long jump (a link, Home key) may cross the header between two observer callbacks
    window.addEventListener('resize', function () { decide(); place(); });
    if (wide.addEventListener) wide.addEventListener('change', decide);
  }

  /* 本章目录跟着正文高亮当前小节；手机上目录默认收起 */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc-side a[href^="#"]'));
  if (tocLinks.length && 'IntersectionObserver' in window) {
    var byId = {}; tocLinks.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
    var seen = {};
    var mark = function () {
      var cur = null;
      tocLinks.forEach(function (a) { var id = a.getAttribute('href').slice(1); if (seen[id]) cur = cur || a; });
      tocLinks.forEach(function (a) { if (a === cur) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
    };
    var io = null;
    var watch = function () {      // the reading band is 15%–30% of the window height, in pixels (percent margins of an observer are not resolved the same way everywhere)
      if (io) io.disconnect(); seen = {};
      var h = window.innerHeight;
      io = new IntersectionObserver(function (es) { es.forEach(function (e) { seen[e.target.id] = e.isIntersecting; }); mark(); }, { rootMargin: '-' + Math.round(h * 0.15) + 'px 0px -' + Math.round(h * 0.70) + 'px 0px' });
      Object.keys(byId).forEach(function (id) { var el = document.getElementById(id); if (el) io.observe(el); });
    };
    watch();
    var lastH = window.innerHeight;
    window.addEventListener('resize', function () { if (Math.abs(window.innerHeight - lastH) > 40) { lastH = window.innerHeight; watch(); } });
  }
  /* 手机上本章目录默认收起；窗口变宽到两栏时重新展开（宽屏上目录标题不可点） */
  var folds = Array.prototype.slice.call(document.querySelectorAll('details.toc-fold'));
  if (narrow.matches) folds.forEach(function (d) { d.removeAttribute('open'); });
  if (narrow.addEventListener) narrow.addEventListener('change', function () { if (!narrow.matches) folds.forEach(function (d) { d.open = true; }); });

  /* 阅读进度；读到九成记“读过” */
  var main = document.querySelector('main[data-unit]');
  var bar = document.getElementById('progress');
  function onScroll() {
    var h = document.documentElement, max = h.scrollHeight - h.clientHeight, pct = max > 0 ? Math.min(100, Math.round((h.scrollTop / max) * 100)) : 0;
    if (bar) bar.style.width = pct + '%';
    if (main && pct >= 90 && store('read.' + main.getAttribute('data-unit')) !== '1') store('read.' + main.getAttribute('data-unit'), '1');
  }
  window.addEventListener('scroll', onScroll, { passive: true }); onScroll();

  /* 目录和书架上的“读过” */
  Array.prototype.forEach.call(document.querySelectorAll('li[data-unit]'), function (li) { if (store('read.' + li.getAttribute('data-unit')) === '1') li.classList.add('read'); });
  Array.prototype.forEach.call(document.querySelectorAll('.book-card'), function (card) {
    var ids = (card.getAttribute('data-units') || '').split(','), n = 0;
    ids.forEach(function (id) { if (store('read.' + id) === '1') n++; });
    var el = card.querySelector('.rd-n'); if (el) el.textContent = String(n); if (n) card.classList.add('has-read');
  });

  /* 浅色／深色 */
  var root = document.documentElement, saved = store('theme');
  if (saved === 'light' || saved === 'dark') root.setAttribute('data-theme', saved);
  var tb = document.getElementById('theme');
  if (tb) tb.addEventListener('click', function () {
    var dark = root.getAttribute('data-theme') ? root.getAttribute('data-theme') === 'dark' : (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark'; root.setAttribute('data-theme', next); store('theme', next);
  });

  /* 搜索：章标题、人话标题、目标，以及已写章节的正文 */
  var q = document.getElementById('q'), hits = document.getElementById('hits'), IDX = window.SEARCH_INDEX || [];
  function snippet(text, term) {
    var i = text.toLowerCase().indexOf(term); if (i < 0) return '';
    var a = Math.max(0, i - 14); return (a > 0 ? '…' : '') + text.slice(a, i + term.length + 40) + '…';
  }
  function render(term) {
    hits.innerHTML = '';
    if (!term) { hits.hidden = true; return; }
    var t = term.toLowerCase(), tx = t.replace(/\s+/g, ''), out = [];
    IDX.forEach(function (u) {
      var score = 0, snip = '';
      if (u.id.toLowerCase().indexOf(t) >= 0) score += 5;
      if (u.t.toLowerCase().indexOf(t) >= 0) score += 4;
      if (u.p.toLowerCase().indexOf(t) >= 0) score += 3;
      if (u.g.toLowerCase().indexOf(t) >= 0) score += 2;
      if (u.x && tx && u.x.toLowerCase().indexOf(tx) >= 0) { score += 1; snip = snippet(u.x, tx); }
      if (score) out.push({ u: u, score: score + (u.w ? 0.5 : 0), snip: snip });
    });
    out.sort(function (a, b) { return b.score - a.score; });
    if (!out.length) { var n = document.createElement('div'); n.className = 'none'; n.textContent = '没有找到。'; hits.appendChild(n); hits.hidden = false; return; }
    out.slice(0, 12).forEach(function (h) {
      var a = document.createElement('a'); a.href = ROOT + 'books/' + h.u.b + '/' + h.u.id + '.html';
      a.textContent = h.u.id + '　' + h.u.t + (h.u.w ? '　（有正文）' : '');
      var s = document.createElement('small'); s.textContent = '第 ' + String(h.u.b).replace(/^b(\d+).*$/, '$1') + ' 册 ' + h.u.bt + ' · ' + (h.snip || h.u.p); a.appendChild(s); hits.appendChild(a);
    });
    hits.hidden = false;
  }
  if (q && hits) {
    q.addEventListener('input', function () { render(q.value.trim()); });
    document.addEventListener('click', function (e) { if (!e.target.closest || !e.target.closest('.search')) hits.hidden = true; });
    q.addEventListener('keydown', function (e) { if (e.key === 'Escape') { hits.hidden = true; q.blur(); } });
  }
})();
