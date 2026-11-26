// Pictures drawn on canvases for the screens of the props (fig3d/props). All wording is a parameter; the defaults are neutral. They are decoration (no real code, no real product UI, no logos);
// anything the reader must read stays a DOM label.
import { canvasTex, rng } from './kit.js';

const FONT = '"Noto Sans CJK SC","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif';
const MONO = '"Noto Sans Mono CJK SC","DejaVu Sans Mono",monospace';

function frame(g, w, h, title, { bar = '#2f3b4a', bg = '#e9edf2' } = {}) {
  g.fillStyle = bg; g.fillRect(0, 0, w, h);
  g.fillStyle = bar; g.fillRect(0, 0, w, h * 0.075);
  g.fillStyle = '#ffffff'; g.font = `${Math.round(h * 0.045)}px ${FONT}`; g.textBaseline = 'middle';
  g.fillText(title, w * 0.02, h * 0.04);
  for (let i = 0; i < 3; i++) { g.fillStyle = ['#e8604c', '#e9b923', '#3cb371'][i]; g.beginPath(); g.arc(w - w * 0.02 - i * w * 0.03, h * 0.0375, h * 0.014, 0, 7); g.fill(); }
}

// the engineering software on the engineer's laptop: a project tree and a block diagram of a control program (abstract boxes and wires)
export function engScreen({ warn = false, title = '工程软件', status = '已连接控制器 · 在线' } = {}) {
  return canvasTex(1024, 640, (g, w, h) => {
    frame(g, w, h, title);
    g.fillStyle = '#d5dbe3'; g.fillRect(0, h * 0.075, w * 0.22, h);
    g.fillStyle = '#3a4656'; g.font = `${h * 0.032}px ${FONT}`;
    ['▾ 项目', '　▾ 控制器 1', '　　· 程序块', '　　· 数据块', '　　· 硬件组态', '　▸ 控制器 2', '　▸ 网络'].forEach((t, i) => g.fillText(t, w * 0.015, h * (0.13 + i * 0.055)));
    // a diagram: rungs of contacts and coils, drawn as simple marks
    g.strokeStyle = '#4a5a70'; g.lineWidth = 3;
    for (let r = 0; r < 6; r++) {
      const y = h * (0.17 + r * 0.13), x0 = w * 0.26, x1 = w * 0.96;
      g.beginPath(); g.moveTo(x0, y); g.lineTo(x1, y); g.stroke();
      g.beginPath(); g.moveTo(x0, y - 20); g.lineTo(x0, y + 20); g.stroke();
      const n = 2 + (r % 3);
      for (let k = 0; k < n; k++) {
        const x = x0 + (k + 1) * (x1 - x0) / (n + 2);
        g.fillStyle = '#e9edf2'; g.fillRect(x - 16, y - 14, 32, 28);
        g.beginPath(); g.moveTo(x - 10, y - 14); g.lineTo(x - 10, y + 14); g.moveTo(x + 10, y - 14); g.lineTo(x + 10, y + 14); g.stroke();
      }
      const xc = x1 - 40; g.fillStyle = '#e9edf2'; g.fillRect(xc - 18, y - 16, 36, 32);
      g.beginPath(); g.arc(xc, y, 14, 0, 7); g.stroke();
    }
    if (warn) { g.fillStyle = 'rgba(231,76,60,0.12)'; g.fillRect(w * 0.24, h * 0.1, w * 0.74, h * 0.86); }
    g.fillStyle = '#5d6b7d'; g.fillRect(0, h * 0.955, w, h * 0.045);
    g.fillStyle = '#fff'; g.font = `${h * 0.028}px ${FONT}`; g.fillText(status, w * 0.015, h * 0.978);
  });
}

// a file window showing what is on the USB stick. hidden: the extra files are hidden (what the user sees); else shown greyed out
export function usbScreen({ showHidden = false } = {}) {
  return canvasTex(1024, 640, (g, w, h) => {
    frame(g, w, h, '可移动磁盘');
    const items = [['文件夹', '#e9b923', 'folder'], ['报告', '#5b8bd0', 'doc'], ['照片', '#58a55c', 'img']];
    if (showHidden) items.push(['（隐藏）', '#9aa3ad', 'lnk'], ['（隐藏）', '#9aa3ad', 'lnk'], ['（隐藏）', '#9aa3ad', 'tmp']);
    items.forEach(([t, c, kind], i) => {
      const x = w * (0.08 + (i % 4) * 0.22), y = h * (0.2 + Math.floor(i / 4) * 0.36);
      g.globalAlpha = kind === 'lnk' || kind === 'tmp' ? 0.55 : 1;
      g.fillStyle = c;
      if (kind === 'folder') { g.fillRect(x, y + 18, 120, 84); g.fillRect(x, y + 6, 54, 20); }
      else { g.fillRect(x + 14, y, 92, 110); g.fillStyle = '#ffffff'; for (let k = 0; k < 4; k++) g.fillRect(x + 26, y + 22 + k * 18, 68, 6); }
      if (kind === 'lnk') { g.fillStyle = '#ffffff'; g.fillRect(x + 14, y + 74, 36, 36); g.strokeStyle = '#2b6cb0'; g.lineWidth = 5; g.beginPath(); g.moveTo(x + 20, y + 104); g.lineTo(x + 44, y + 80); g.moveTo(x + 30, y + 80); g.lineTo(x + 44, y + 80); g.lineTo(x + 44, y + 94); g.stroke(); }
      g.globalAlpha = 1;
      g.fillStyle = '#2b3440'; g.font = `${h * 0.04}px ${FONT}`; g.fillText(t, x + 8, y + 140);
    });
  });
}

// the operator's overview of a cascade: one dot per centrifuge (green running, grey isolated), a flat trend line and a status bar
export function scadaScreen({ rows = 4, cols = 20, grey = [], alarm = false, label = '运行正常', title = '监控画面', trendTitle = '趋势', readings = [['平均频率', '1064'], ['压力', '正常']], trend = 'flat', seed = 3 } = {}) {
  return canvasTex(1280, 720, (g, w, h) => {
    g.fillStyle = '#16202b'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#24364a'; g.fillRect(0, 0, w, h * 0.08);
    g.fillStyle = '#dfe9f3'; g.font = `${h * 0.045}px ${FONT}`; g.textBaseline = 'middle'; g.fillText(title, w * 0.02, h * 0.04);
    g.fillStyle = alarm ? '#e74c3c' : '#2ecc71'; g.fillRect(w * 0.7, h * 0.015, w * 0.28, h * 0.05);
    g.fillStyle = '#0d1520'; g.font = `bold ${h * 0.036}px ${FONT}`; g.fillText(label, w * 0.71, h * 0.04);
    // pipes and dots
    const x0 = w * 0.06, x1 = w * 0.94, y0 = h * 0.17, dy = h * 0.1;
    for (let r = 0; r < rows; r++) {
      const y = y0 + r * dy;
      g.strokeStyle = '#3d556e'; g.lineWidth = 3; g.beginPath(); g.moveTo(x0, y); g.lineTo(x1, y); g.stroke();
      for (let c = 0; c < cols; c++) {
        const x = x0 + (c + 0.5) * (x1 - x0) / cols;
        const isGrey = grey.some(([a, b]) => a === r && b === c);
        g.fillStyle = isGrey ? '#7f8c8d' : '#2ecc71'; g.beginPath(); g.arc(x, y, h * 0.018, 0, 7); g.fill();
      }
    }
    // trend panel
    const ty = h * 0.62, th = h * 0.3;
    g.strokeStyle = '#3d556e'; g.lineWidth = 2; g.strokeRect(w * 0.06, ty, w * 0.6, th);
    g.fillStyle = '#9fb3c8'; g.font = `${h * 0.032}px ${FONT}`; g.fillText(trendTitle, w * 0.07, ty + h * 0.03);
    g.strokeStyle = '#7cc4ff'; g.lineWidth = 4; g.beginPath();
    const R = rng(seed);
    for (let i = 0; i <= 60; i++) {
      const x = w * 0.07 + i * (w * 0.58) / 60;
      let v = 0.5 + (R() - 0.5) * 0.03;
      if (trend === 'wild') v = 0.5 + Math.sin(i / 4) * 0.35 + (R() - 0.5) * 0.06;
      const y = ty + th * (1 - v);
      if (i) g.lineTo(x, y); else g.moveTo(x, y);
    }
    g.stroke();
    // readings box
    g.strokeStyle = '#3d556e'; g.strokeRect(w * 0.7, ty, w * 0.24, th);
    g.fillStyle = '#9fb3c8'; g.font = `${h * 0.032}px ${FONT}`;
    readings.slice(0, 2).forEach(([k], i) => g.fillText(k, w * 0.72, ty + h * (0.05 + i * 0.12)));
    g.fillStyle = '#e8f1fa'; g.font = `bold ${h * 0.06}px ${MONO}`;
    readings.slice(0, 2).forEach(([, v], i) => g.fillText(v, w * 0.72, ty + h * (0.1 + i * 0.12)));
  });
}

// a malware analyst's screen: a dump of bytes (random hex, decoration only) and a panel of findings
export function analystScreen({ seed = 7, title = '样本分析', heading = '发现', findings = [], mark = -1 } = {}) {
  return canvasTex(1280, 720, (g, w, h) => {
    frame(g, w, h, title, { bar: '#20262e', bg: '#111418' });
    const R = rng(seed);
    g.font = `${h * 0.03}px ${MONO}`; g.textBaseline = 'top';
    for (let r = 0; r < 18; r++) {
      g.fillStyle = '#5d6b7d'; g.fillText((r * 16).toString(16).padStart(6, '0'), w * 0.02, h * (0.11 + r * 0.047));
      for (let c = 0; c < 12; c++) {
        const v = Math.floor(R() * 256).toString(16).padStart(2, '0');
        g.fillStyle = (r === 6 && c > 2 && c < 9) ? '#3cf2a0' : '#9fb3c8';
        g.fillText(v, w * (0.1 + c * 0.036), h * (0.11 + r * 0.047));
      }
    }
    g.fillStyle = '#1b2129'; g.fillRect(w * 0.58, h * 0.11, w * 0.4, h * 0.84);
    g.fillStyle = '#e8f1fa'; g.font = `bold ${h * 0.04}px ${FONT}`; g.fillText(heading, w * 0.6, h * 0.14);
    g.font = `${h * 0.034}px ${FONT}`;
    findings.forEach((t, i) => { g.fillStyle = i === mark ? '#ffd166' : '#c8d6e5'; g.fillText('· ' + t, w * 0.6, h * (0.23 + i * 0.08)); });
  });
}

// seven-segment style digits on a drive's display
export function vfdDisplay(text = '1064', unit = 'Hz', { color = '#ff5a3c', bg = '#140707' } = {}) {
  return canvasTex(512, 200, (g, w, h) => {
    g.fillStyle = bg; g.fillRect(0, 0, w, h);
    g.fillStyle = color; g.font = `bold ${h * 0.7}px ${MONO}`; g.textBaseline = 'middle'; g.textAlign = 'right';
    g.shadowColor = color; g.shadowBlur = 18;
    g.fillText(text, w * 0.78, h * 0.55);
    g.font = `bold ${h * 0.28}px ${MONO}`; g.textAlign = 'left'; g.fillText(unit, w * 0.81, h * 0.66);
  });
}

// the printed face of a pass (a code-signing certificate drawn as an ID card). No real company name or logo on it.
export function passFace({ who = '甲', revoked = false, tone = '#1D4F8F', title = '数字证书', holder = null, purpose = '用途：签名', issuer = '签发：证书机构', revokedText = '已 吊 销' } = {}) {
  return canvasTex(640, 400, (g, w, h) => {
    g.fillStyle = '#fffdf6'; g.fillRect(0, 0, w, h);
    g.fillStyle = tone; g.fillRect(0, h * 0.13, w, h * 0.17);
    g.fillStyle = '#ffffff'; g.font = `bold ${h * 0.095}px ${FONT}`; g.textBaseline = 'middle'; g.fillText(title, w * 0.05, h * 0.215);
    g.fillStyle = '#d9d4c7'; g.fillRect(w * 0.05, h * 0.36, w * 0.24, h * 0.44);
    g.fillStyle = '#9b9686'; g.beginPath(); g.arc(w * 0.17, h * 0.5, h * 0.08, 0, 7); g.fill(); g.fillRect(w * 0.085, h * 0.62, w * 0.17, h * 0.16);
    g.fillStyle = '#2b3440'; g.font = `${h * 0.075}px ${FONT}`;
    g.fillText(holder || `持证：${who}`, w * 0.34, h * 0.42);
    g.fillText(purpose, w * 0.34, h * 0.55);
    g.fillText(issuer, w * 0.34, h * 0.68);
    g.fillStyle = '#8a8578'; g.font = `${h * 0.055}px ${MONO}`; g.fillText('SERIAL  ··· ··· ···', w * 0.05, h * 0.9);
    if (revoked) {
      g.save(); g.translate(w * 0.5, h * 0.55); g.rotate(-0.25);
      g.strokeStyle = '#BB2A2A'; g.lineWidth = 12; g.strokeRect(-w * 0.32, -h * 0.13, w * 0.64, h * 0.26);
      g.fillStyle = '#BB2A2A'; g.font = `bold ${h * 0.17}px ${FONT}`; g.textAlign = 'center'; g.fillText(revokedText, 0, 4);
      g.restore();
    }
  });
}

// the PLC's little label strip / module front print
export function moduleFace(title, { tone = '#2b3440' } = {}) {
  return canvasTex(128, 512, (g, w, h) => {
    g.fillStyle = '#e7e9ec'; g.fillRect(0, 0, w, h);
    g.fillStyle = tone; g.fillRect(0, 0, w, h * 0.07);
    g.save(); g.translate(w * 0.62, h * 0.55); g.rotate(-Math.PI / 2);
    g.fillStyle = '#2b3440'; g.font = `bold ${w * 0.3}px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(title, 0, 0);
    g.restore();
  });
}

// a scrap of "code" for the worm's body: random hex pairs and bars (decoration only, not real code)
export function codeShard({ seed = 1, color = '#3cf2a0', bg = 'rgba(6,20,14,0.92)' } = {}) {
  return canvasTex(256, 160, (g, w, h) => {
    const R = rng(seed);
    g.fillStyle = bg; g.fillRect(0, 0, w, h);
    g.fillStyle = color; g.font = `bold ${h * 0.17}px ${MONO}`; g.textBaseline = 'top';
    for (let r = 0; r < 4; r++) {
      let s = '';
      for (let c = 0; c < 5; c++) s += Math.floor(R() * 256).toString(16).padStart(2, '0') + ' ';
      g.globalAlpha = 0.55 + R() * 0.45;
      g.fillText(s, w * 0.05, h * (0.08 + r * 0.22));
    }
    g.globalAlpha = 1;
    g.strokeStyle = color; g.lineWidth = 4; g.strokeRect(2, 2, w - 4, h - 4);
  });
}

// the beetle's back screen: a calm flat line and the word 正常 (the mask it shows)
export function maskScreen({ word = '正常' } = {}) {
  return canvasTex(256, 160, (g, w, h) => {
    g.fillStyle = '#0f1c14'; g.fillRect(0, 0, w, h);
    g.strokeStyle = '#2ecc71'; g.lineWidth = 6; g.beginPath(); g.moveTo(10, h * 0.62);
    for (let x = 10; x < w - 10; x += 8) g.lineTo(x, h * 0.62 + Math.sin(x * 0.2) * 2);
    g.stroke();
    g.fillStyle = '#2ecc71'; g.font = `bold ${h * 0.3}px ${FONT}`; g.textBaseline = 'top'; g.fillText(word, w * 0.08, h * 0.08);
  });
}
