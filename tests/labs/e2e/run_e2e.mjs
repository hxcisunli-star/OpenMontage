#!/usr/bin/env node
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import {spawn, execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

// E2E_OUT_ROOT: where out/ (results, screenshots) goes; E2E_TOOLS: the folder with serve.mjs, set_labs.py and the lab files (default: the layout of the Codex workspace)
const workspace = process.env.E2E_OUT_ROOT ? path.resolve(process.env.E2E_OUT_ROOT) : path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const toolsRoot = process.env.E2E_TOOLS ? path.resolve(process.env.E2E_TOOLS) : path.join(workspace, 'ref/docs/whiteboard/ebook');
const python = '/home/MyProject/OpenMontage/.venv/bin/python';
const rendererRoot = '/home/MyProject/OpenMontage/remotion-composer/node_modules';
const require = createRequire(import.meta.url);
const renderer = require(rendererRoot + '/@remotion/renderer');
const {Log} = require(rendererRoot + '/@remotion/renderer/dist/logger.js');
const rendererError = Log.error;
Log.error = function (options, ...messages) {
  // CDP diagnostics below retain every resource error; avoid duplicate renderer output with temporary locations.
  if (messages.some((message) => String(message).includes('Failed to load resource:'))) return;
  return rendererError.call(this, options, ...messages);
};
const chrome = rendererRoot + '/.remotion/chrome-headless-shell/linux64/chrome-headless-shell-linux64/chrome-headless-shell';
const labId = 's2-u01-draw';
const chapterPath = 'books/b2-llm/S2-U01.html';
const prefix = '#lab-' + labId + '-';
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const assert = (ok, message) => { if (!ok) throw new Error(message); };
const ev = (page, fn, ...args) => page.evaluate(fn, ...args);
const tests = [];
function test(name, fn, options = {}) { tests.push({name, fn, options}); }

function parseArgs(argv) {
  let site = path.join(workspace, 'site');
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--site' && argv[i + 1]) site = path.resolve(argv[++i]);
    else if (argv[i] === '--help' || argv[i] === '-h') {
      process.stdout.write('用法：node tests/labs/e2e/run_e2e.mjs [--site DIR]\n');
      process.exit(0);
    } else throw new Error('未知参数或缺少参数值：' + argv[i]);
  }
  return {site};
}

async function waitFor(predicate, timeout = 10000, label = '页面条件') {
  const deadline = Date.now() + timeout;
  let value;
  while (Date.now() < deadline) {
    value = await predicate();
    if (value) return value;
    await pause(40);
  }
  throw new Error(label + '超时；最后值：' + JSON.stringify(value));
}

async function freePort() {
  const socket = net.createServer();
  await new Promise((resolve, reject) => { socket.once('error', reject); socket.listen(0, '127.0.0.1', resolve); });
  const port = socket.address().port;
  await new Promise((resolve) => socket.close(resolve));
  return port;
}

async function startServer(site, temporary) {
  const config = path.join(temporary, 'serve.json');
  const port = await freePort();
  const output = execFileSync(process.execPath, [path.join(toolsRoot, 'serve.mjs'), 'init', '--config', config, '--root', site,
    '--host', '127.0.0.1', '--port', String(port), '--san-ip', '127.0.0.1'], {encoding: 'utf8'});
  const match = /^password: (.+)$/m.exec(output);
  assert(match, '服务器初始化未返回临时认证');
  const authorization = 'Basic ' + Buffer.from('reader:' + match[1]).toString('base64');
  const origin = 'https:' + '//127.0.0.1:' + port;
  const child = spawn(process.execPath, [path.join(toolsRoot, 'serve.mjs'), 'run', '--config', config], {stdio: ['ignore', 'pipe', 'pipe']});
  let stderr = '';
  child.stderr.on('data', (chunk) => { stderr += chunk; });
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('临时服务器启动超时：' + stderr)), 10000);
      child.stdout.once('data', () => { clearTimeout(timer); resolve(); });
      child.once('error', (error) => { clearTimeout(timer); reject(error); });
      child.once('exit', (code) => { clearTimeout(timer); reject(new Error('临时服务器退出：' + code + ' ' + stderr)); });
    });
  } catch (error) { child.kill(); throw error; }
  return {origin, authorization, password: match[1], async close() {
    if (child.exitCode === null) {
      const exited = new Promise((resolve) => child.once('exit', resolve));
      child.kill('SIGTERM');
      await exited;
    }
  }};
}

function safeUrl(url, ctx) {
  try {
    const parsed = new URL(url);
    if (parsed.origin === ctx.server.origin) return parsed.pathname;
    if (parsed.protocol === 'file:') return '/' + path.relative(ctx.site, parsed.pathname).split(path.sep).join('/');
    if (parsed.protocol === 'data:' || parsed.protocol === 'about:') return parsed.protocol;
    return parsed.protocol + '<站外请求>';
  } catch (_) { return String(url || ''); }
}

function expectedResource(url, ctx) {
  const pathname = safeUrl(url, ctx);
  if (/^\/media\/S2-U01\/(frames\/f(?:0[1-9]|10)\.jpg|output\.mp4)$/.test(pathname)) return '提供的站点缺少媒体文件';
  if (ctx.expected.has(pathname)) return ctx.expected.get(pathname);
  return null;
}

function monitorSession(session, ctx, label) {
  const requestUrls = new Map();
  session.on('Network.requestWillBeSent', ({request, requestId}) => {
    requestUrls.set(requestId, request.url);
    ctx.diag.requests.push({label, path: safeUrl(request.url, ctx)});
  });
  session.on('Network.responseReceived', ({response}) => {
    if (response.status >= 400) ctx.diag.responses.push({label, path: safeUrl(response.url, ctx), status: response.status, expected: expectedResource(response.url, ctx)});
  });
  session.on('Network.loadingFailed', (entry) => {
    if (!entry.canceled) {
      const url = requestUrls.get(entry.requestId);
      ctx.diag.loadingFailures.push({label, path: safeUrl(url, ctx), text: entry.errorText, blockedReason: entry.blockedReason || null, expected: expectedResource(url, ctx)});
    }
  });
  session.on('Log.entryAdded', ({entry}) => {
    if (entry.level === 'error' || entry.level === 'warning') ctx.diag.logs.push({label, level: entry.level, source: entry.source,
      text: entry.text, path: safeUrl(entry.url, ctx), expected: expectedResource(entry.url, ctx)});
  });
  session.on('Runtime.consoleAPICalled', (entry) => {
    if (entry.type === 'error' || entry.type === 'warning') ctx.diag.logs.push({label, level: entry.type, source: 'console',
      text: entry.args.map((arg) => arg.value || arg.description || '').join(' '), expected: null});
  });
  session.on('Runtime.exceptionThrown', ({exceptionDetails: entry}) => {
    ctx.diag.exceptions.push({label, text: entry.exception && (entry.exception.description || entry.exception.value) || entry.text});
  });
}

function preload() {
  window.__E2E = {csp: [], workers: 0, results: [], guardListeners: 0};
  document.addEventListener('securitypolicyviolation', function (event) {
    window.__E2E.csp.push({directive: event.violatedDirective, blocked: event.blockedURI});
  });
  const originalAdd = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    if (this.classList && this.classList.contains('lab-work') && (opts === true || opts && opts.capture) &&
        ['paste', 'drop', 'dragover', 'keydown', 'beforeinput', 'contextmenu', 'copy', 'cut', 'dragstart'].indexOf(type) >= 0) window.__E2E.guardListeners += 1;
    return originalAdd.call(this, type, fn, opts);
  };
  const NativeWorker = window.Worker;
  window.Worker = function (...args) {
    const worker = new NativeWorker(...args);
    window.__E2E.workers += 1;
    worker.addEventListener('message', function (event) {
      if (event.data && event.data.type === 'run-result') window.__E2E.results.push(event.data);
      if (event.data && event.data.type === 'init-ok') window.__E2E.pythonVersion = event.data.pythonVersion;
    });
    return worker;
  };
  window.Worker.prototype = NativeWorker.prototype;
}

async function newPage(ctx) {
  const page = await ctx.browser.newPage({context: undefined, logLevel: 'error', indent: false, pageIndex: 0, onBrowserLog: null, onLog: () => {}});
  ctx.pages.push(page);
  const client = page._client();
  if (!ctx.runtime.chrome) {
    const {value: version} = await client.send('Browser.getVersion');
    ctx.runtime.chrome = version.product;
    ctx.runtime.js = version.jsVersion;
  }
  monitorSession(client, ctx, 'page');
  page.on('error', (error) => ctx.diag.exceptions.push({label: 'page', text: String(error)}));
  client.on('Target.attachedToTarget', (event) => {
    if (event.targetInfo.type !== 'worker') return;
    const session = client.connection().session(event.sessionId);
    if (!session) { ctx.diag.exceptions.push({label: 'monitor', text: '无法取得 Worker CDP 会话'}); return; }
    monitorSession(session, ctx, 'worker');
    ctx.sessions.push(session);
    const task = (async () => {
      try {
        await session.send('Network.enable');
        if (ctx.options.blocked) await session.send('Network.setBlockedURLs', {urls: ctx.options.blocked});
        await session.send('Network.setExtraHTTPHeaders', {headers: {Authorization: ctx.server.authorization}});
        await session.send('Runtime.enable');
        await session.send('Log.enable');
      } catch (error) {
        if (!ctx.closing) ctx.diag.exceptions.push({label: 'monitor', text: String(error)});
      } finally { await session.send('Runtime.runIfWaitingForDebugger').catch(() => {}); }
    })();
    ctx.workerTasks.push(task);
  });
  await client.send('Security.setIgnoreCertificateErrors', {ignore: true});
  await client.send('Network.enable');
  await client.send('Network.setCacheDisabled', {cacheDisabled: true});
  await client.send('Network.setExtraHTTPHeaders', {headers: {Authorization: ctx.server.authorization}});
  await client.send('Log.enable');
  await client.send('Runtime.enable');
  await client.send('Target.setAutoAttach', {autoAttach: true, waitForDebuggerOnStart: true, flatten: true});
  await client.send('Page.addScriptToEvaluateOnNewDocument', {source: '(' + preload.toString() + ')()'});
  const {value: clear} = await client.send('Page.addScriptToEvaluateOnNewDocument', {source: 'try {localStorage.clear();} catch (_) {}'});
  if (ctx.options.blocked) await client.send('Network.setBlockedURLs', {urls: ctx.options.blocked});
  await page.setViewport({width: ctx.options.width || 1000, height: 900, deviceScaleFactor: 1});
  await client.send('Page.bringToFront');
  await page.goto({url: ctx.options.offline ? pathToFileURL(path.join(ctx.site, chapterPath)).href : ctx.server.origin + '/' + chapterPath, timeout: 30000});
  await client.send('Page.removeScriptToEvaluateOnNewDocument', {identifier: clear.identifier});
  await initialized(page);
  await ev(page, () => {
    window.__E2E.guardInstalls = 0;
    const original = LabGuard.install;
    LabGuard.install = function (...args) { window.__E2E.guardInstalls += 1; return original.apply(this, args); };
  });
  return page;
}

async function initialized(page) {
  await waitFor(() => ev(page, (id) => Boolean(window.__EBOOK_LABS__ && window.__EBOOK_LABS__.instances.get(id)), labId), 10000, '练习初始化');
}
async function reload(ctx, page) {
  await page.goto({url: ctx.server.origin + '/' + chapterPath, timeout: 30000});
  await initialized(page);
}
async function hook(page, method, ...values) {
  return ev(page, ({method, values, id}) => window.__EBOOK_LABS__.instances.get(id)[method](...values), {method, values, id: labId});
}
async function click(page, action) {
  await ev(page, (selector) => {
    const element = document.querySelector(selector);
    if (!element || element.hidden || element.disabled) throw new Error('按钮不可用：' + selector);
    element.click();
  }, prefix + action);
}
async function waitState(page, state, timeout = 30000) {
  return waitFor(async () => (await hook(page, 'getState')) === state, timeout, '状态 ' + state);
}
async function begin(page) {
  await ev(page, () => {
    const section = document.querySelector('section.lab');
    window.__E2E.states = [section.dataset.labState];
    window.__E2E.statuses = [];
    new MutationObserver(() => { window.__E2E.states.push(section.dataset.labState); }).observe(section, {attributes: true, attributeFilter: ['data-lab-state']});
    new MutationObserver(() => { window.__E2E.statuses.push(section.querySelector('.lab-status').textContent); }).observe(section.querySelector('.lab-status'), {childList: true, subtree: true, characterData: true});
  });
  await click(page, 'start');
  await waitFor(async () => ['ready', 'error'].includes(await hook(page, 'getState')), 60000, '启动完成');
  const data = await info(page);
  assert(data.state === 'ready', '启动失败：' + data.note);
}
async function info(page) {
  return ev(page, (id) => {
    const instance = window.__EBOOK_LABS__.instances.get(id);
    const section = document.querySelector('section.lab');
    const get = (suffix) => document.getElementById('lab-' + id + '-' + suffix);
    const model = instance.editor && instance.editor.getModel();
    const spec = JSON.parse(section.querySelector('.lab-spec').textContent);
    return {state: instance.getState(), code: instance.getCode(), spec, language: model && model.getLanguageId(),
      lineNumbers: Boolean(section.querySelector('.monaco-editor .line-numbers')), guard: section.dataset.pasteGuard,
      status: get('status').textContent, stdout: get('stdout').textContent, error: get('error').textContent, errorHidden: get('error').hidden,
      note: get('note').textContent, startHidden: get('start').hidden, startText: get('start').textContent, previewHidden: get('preview').hidden,
      doneHidden: get('done').hidden, done: get('done').textContent, stopHidden: get('stop').hidden, runDisabled: get('run').disabled,
      checks: Array.from(get('checks').children).map((li) => ({id: li.dataset.checkId, passed: li.dataset.passed, text: li.textContent})),
      markers: model ? monaco.editor.getModelMarkers({resource: model.uri}).map((m) => ({line: m.startLineNumber, column: m.startColumn, message: m.message})) : [],
      hints: Array.from(get('hints').children).map((item) => item.textContent), hintText: get('hint').textContent,
      solutionButtonHidden: get('solution-btn').hidden, solutionHidden: get('solution').hidden, solution: get('solution').textContent,
      toast: get('toast').textContent, toastHidden: get('toast').hidden, resetText: get('reset').textContent,
      classes: section.querySelector('.monaco-editor') ? section.querySelector('.monaco-editor').className : '',
      probe: window.__E2E};
  }, labId);
}
async function runButton(page, action = 'run') {
  await click(page, action);
  await waitState(page, 'ready', 30000);
  return info(page);
}
async function focus(page) {
  await page._client().send('Page.bringToFront');
  await ev(page, async (id) => {
    const instance = window.__EBOOK_LABS__.instances.get(id);
    instance.editor.getDomNode().scrollIntoView({block: 'center', behavior: 'instant'});
    instance.editor.focus();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }, labId);
}
async function key(page, keyName, code, modifiers = 0, command) {
  const virtuals = {KeyA: 65, KeyC: 67, KeyX: 88, KeyV: 86, KeyZ: 90, KeyY: 89, Insert: 45, Backspace: 8, Enter: 13, ArrowRight: 39, Escape: 27};
  const data = {key: keyName, code, modifiers, windowsVirtualKeyCode: virtuals[code] || 0};
  if (command) data.commands = [command];
  await page._client().send('Input.dispatchKeyEvent', Object.assign({type: 'keyDown'}, data));
  delete data.commands;
  await page._client().send('Input.dispatchKeyEvent', Object.assign({type: 'keyUp'}, data));
}
async function selectAll(page) { await focus(page); await key(page, 'a', 'KeyA', 2, 'selectAll'); }
async function typeText(page, value) {
  await selectAll(page);
  await key(page, 'Backspace', 'Backspace');
  let typed = '';
  for (const character of value) {
    typed += character;
    await page._client().send('Input.insertText', {text: character});
    // Remove only the suffix Monaco just supplied (closing quotes/brackets or indentation).
    // The requested characters always enter through real browser text input.
    const suppliedSuffix = await ev(page, ({id, expected}) => {
      const editor = window.__EBOOK_LABS__.instances.get(id).editor;
      const model = editor.getModel();
      const actual = model.getValue();
      if (!actual.startsWith(expected)) throw new Error('逐字输入前缀不一致：' + JSON.stringify({expected, actual}));
      if (actual.length === expected.length) return false;
      const start = model.getPositionAt(expected.length), end = model.getPositionAt(actual.length);
      editor.setSelection({startLineNumber: start.lineNumber, startColumn: start.column, endLineNumber: end.lineNumber, endColumn: end.column});
      return true;
    }, {id: labId, expected: typed});
    if (suppliedSuffix) await key(page, 'Backspace', 'Backspace');
  }
  assert(await hook(page, 'getCode') === value, '浏览器逐字输入结果不一致：' + JSON.stringify(await hook(page, 'getCode')));
}
async function clipboard(page, value) {
  await focus(page);
  await page._client().send('Browser.grantPermissions', {permissions: ['clipboardReadWrite', 'clipboardSanitizedWrite'], origin: new URL(page.url()).origin});
  await ev(page, async (text) => { await navigator.clipboard.writeText(text); }, value);
  const actual = await ev(page, async () => navigator.clipboard.readText());
  assert(actual === value, '系统剪贴板写入失败');
}
async function paste(page, value, variant = 'ctrl') {
  await clipboard(page, value);
  await focus(page);
  if (variant === 'shift') await key(page, 'Insert', 'Insert', 8, 'paste');
  else await key(page, 'v', 'KeyV', 2, variant === 'command' ? 'paste' : undefined);
}
async function drag(page, value) {
  await focus(page);
  const point = await ev(page, () => {
    const rect = document.querySelector('.monaco-editor .view-lines').getBoundingClientRect();
    return {x: rect.left + 20, y: rect.top + 10};
  });
  const data = {items: [{mimeType: 'text/plain', data: value}], files: [], dragOperationsMask: 1};
  for (const type of ['dragEnter', 'dragOver', 'drop']) {
    await page._client().send('Input.dispatchDragEvent', Object.assign({type, data}, point));
  }
}
async function contextMenu(page) {
  await focus(page);
  const box = await ev(page, () => {
    const r = document.querySelector('.monaco-editor .view-lines').getBoundingClientRect();
    return {x: r.left + 30, y: r.top + 10};
  });
  for (const type of ['mousePressed', 'mouseReleased']) await page._client().send('Input.dispatchMouseEvent', {type, x: box.x, y: box.y, button: 'right', clickCount: 1});
  await ev(page, () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  return ev(page, () => {
    function visibleMenu(root) {
      if (Array.from(root.querySelectorAll('.monaco-menu, .monaco-menu-container')).some((node) => node.getBoundingClientRect().height > 0)) return true;
      return Array.from(root.querySelectorAll('*')).some((node) => node.shadowRoot && visibleMenu(node.shadowRoot));
    }
    const visible = visibleMenu(document);
    window.__E2E.menuVisible = visible;
    return visible;
  });
}
async function capture(ctx, page, name) {
  await ev(page, async () => {
    document.querySelector('section.lab').scrollIntoView({block: 'center', behavior: 'instant'});
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const {value: data} = await page._client().send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
  const filename = 'out/shots/' + name + '.png';
  await fs.writeFile(path.join(workspace, filename), Buffer.from(data.data, 'base64'));
  if (!ctx.shots.includes(filename)) ctx.shots.push(filename);
}
async function config(ctx, blocked) {
  try {
    execFileSync(python, [path.join(toolsRoot, 'set_labs.py'), '--site-dir', ctx.site, '--no-yaml', '--paste', blocked ? 'block' : 'allow'], {encoding: 'utf8', stdio: 'pipe', env: Object.assign({}, process.env, {PYTHONDONTWRITEBYTECODE: '1'})});
  } catch (error) {
    if (!String(error.stderr).includes("No module named 'labs'")) throw error;
    ctx.notes.push('原版 set_labs.py 缺少 labs 模块，独立 H0 用例记录失败；本用例用等价 JSON 写入继续验证浏览器开关。');
    await fs.writeFile(path.join(ctx.site, 'assets/lab-config.json'), JSON.stringify({block_paste: blocked}) + '\n');
  }
}
async function ready(ctx) { const page = await newPage(ctx); await begin(page); return page; }

// Every registered case gets independent pages, diagnostics, storage and a restored config.
test('A 基本流程与五项检查', async (ctx) => {
  const page = await newPage(ctx);
  assert((await info(page)).state === 'idle', '开始前不是 idle');
  assert(!ctx.diag.requests.some((r) => r.path.includes('/vendor/')), '开始前请求了 vendor');
  await begin(page);
  const initial = await info(page);
  assert(initial.probe.states.includes('loading') && initial.probe.states.includes('ready'), '缺少 loading/ready 状态');
  assert(initial.probe.statuses.includes('正在加载编辑器 (1/2)…') && initial.probe.statuses.includes('正在启动 Python (2/2)…'), '加载文案或顺序不符合合同');
  const tokens = await ev(page, () => monaco.editor.tokenize('import random\nfor x in range(3):\n    print(x)', 'python'));
  assert(/^3\.12\./.test(initial.probe.pythonVersion), 'Worker Python 版本错误：' + initial.probe.pythonVersion);
  assert(initial.language === 'python' && initial.lineNumbers && tokens.some((line) => line.some((t) => /keyword/.test(t.type))), 'Python、行号或关键字 token 缺失');
  await typeText(page, initial.spec.solution);
  let result = await runButton(page);
  const words = ['小猫', '小狗', '小鸟'];
  const lines = result.stdout.trim().split(/\r?\n/);
  assert(result.errorHidden && lines.length === 3 && lines.every((line) => words.includes(line)), '三行输出错误：' + JSON.stringify({lines, error: result.error, code: result.code}));
  result = await runButton(page, 'check');
  assert(result.checks.length === 5 && result.checks.every((c) => c.passed === 'true'), '五项检查未全过：' + JSON.stringify(result.checks));
  assert(!result.doneHidden && result.done === '已完成 ✓' && result.status === '全部通过 ✓', '缺少完成标识');
  await capture(ctx, page, 'passed');
});

for (const [name, code, pattern, line, column] of [
  ['B1 起始填空 NameError', null, /没填的空白/, 5, null],
  ['B2 全角括号列标记', 'print（"小猫"）\n', /第 1 行第 6 列.*全角标点.*半角/, 1, 6],
  ['B3 缩进错误', 'for i in range(2):\nprint(i)\n', /缩进/, 2, null],
  ['B4 除零与过滤栈帧', 'def divide():\n    return 1 / 0\ndivide()\n', /除数不能是 0/, 2, null]
]) test(name, async (ctx) => {
  const page = await ready(ctx);
  if (code !== null) await hook(page, 'setCode', code);
  const result = await runButton(page);
  assert(!result.errorHidden && pattern.test(result.error) && result.error.includes('第 ' + line + ' 行'), '提示或行号错误：' + result.error);
  assert(result.markers.some((m) => m.line === line && (column === null || m.column === column)), '缺少正确行列 markers：' + JSON.stringify(result.markers));
  const raw = result.probe.results[result.probe.results.length - 1];
  assert(raw && raw.error && raw.error.traceback && !/lab-runner|pyodide|run_request/.test(raw.error.traceback), '未获得过滤后的真实 traceback');
  if (name.startsWith('B4')) {
    assert(raw.error.traceback.includes('line 2') && raw.error.traceback.includes('line 3'), '学生调用栈帧缺失');
    await capture(ctx, page, 'error');
  }
  await hook(page, 'setCode', 'print(1)\n');
  assert((await info(page)).markers.length === 0, '编辑后标记未清除');
});

test('C1 十秒超时与 Worker 重建', async (ctx) => {
  const page = await ready(ctx);
  const before = (await info(page)).probe.workers;
  await hook(page, 'setCode', 'while True:\n    pass\n');
  const started = Date.now();
  await click(page, 'run'); await waitState(page, 'running');
  const running = await info(page);
  assert(!running.stopHidden && running.runDisabled && running.status === '运行中…', '运行按钮状态错误');
  await waitState(page, 'ready', 13000);
  const elapsed = Date.now() - started;
  const timed = await info(page);
  assert(timed.status === '已超时（10 秒），代码已停止' && elapsed >= 9800 && elapsed < 13000, '超时文案或时间错误：' + timed.status + ' / ' + elapsed);
  await typeText(page, 'print("恢复")\n');
  const result = await runButton(page);
  assert(result.stdout === '恢复\n' && result.probe.workers > before, '超时后不能编辑、重建 Worker 或运行');
});
test('C2 停止按钮与再次运行', async (ctx) => {
  const page = await ready(ctx);
  await hook(page, 'setCode', 'while True:\n    pass\n');
  await click(page, 'run'); await waitState(page, 'running'); await click(page, 'stop');
  let result = await info(page);
  assert(result.state === 'ready' && result.status === '已停止' && result.stopHidden && !result.runDisabled, '停止状态错误');
  await hook(page, 'setCode', 'print("再次运行")\n'); result = await runButton(page);
  assert(result.stdout === '再次运行\n', '停止后再次运行失败');
});
test('C3 输出截断与页面响应', async (ctx) => {
  const page = await ready(ctx);
  await hook(page, 'setCode', 'for i in range(50000):\n    print(i)\n');
  const result = await runButton(page);
  assert(result.stdout.endsWith('……输出太长，已截断\n') && result.stdout.split('\n').length === 202, '输出未按 200 行截断');
  assert(result.probe.results[result.probe.results.length - 1].truncated === true, '运行器未报告 truncated');
  await typeText(page, 'print(123)');
  assert((await runButton(page)).stdout === '123\n', '截断后页面不能继续操作');
});
test('C4 input 友好提示', async (ctx) => {
  const page = await ready(ctx); await hook(page, 'setCode', 'input("输入")');
  assert((await runButton(page)).error.includes('页内练习不支持 input() 输入：请直接把值写进变量'), 'input 提示错误');
});

test('D1 草稿刷新恢复', async (ctx) => {
  const page = await ready(ctx); const code = 'print("草稿")\n'; await typeText(page, code);
  await waitFor(() => ev(page, (id) => { const data = JSON.parse(localStorage.getItem('ebook.lab.v1.' + id) || 'null'); return data && data.code === 'print("草稿")\n'; }, labId), 3000, '500 ms 草稿落盘');
  await reload(ctx, page); await begin(page);
  assert(await hook(page, 'getCode') === code, '刷新后草稿丢失');
});
test('D2 两步重置清除通过标记', async (ctx) => {
  const page = await ready(ctx); await hook(page, 'setCode', (await info(page)).spec.solution); await runButton(page, 'check');
  const code = await hook(page, 'getCode'); await click(page, 'reset');
  assert((await info(page)).resetText === '确认重置？' && await hook(page, 'getCode') === code, '第一次重置改变代码');
  await click(page, 'reset'); const result = await info(page);
  assert(result.code === result.spec.starter && result.stdout === '' && result.errorHidden && result.markers.length === 0 && result.doneHidden, '第二次重置未清空状态');
});
test('D3 重置确认三秒自动还原', async (ctx) => {
  const page = await ready(ctx); await hook(page, 'setCode', 'print("保持")');
  await click(page, 'reset'); const started = Date.now();
  assert((await info(page)).resetText === '确认重置？', '没有进入确认状态');
  await waitFor(async () => (await info(page)).resetText === '重置', 4000, '三秒确认过期');
  assert(Date.now() - started >= 2800 && await hook(page, 'getCode') === 'print("保持")', '确认过早结束或改变代码');
});

test('E1 逐条提示解锁参考写法', async (ctx) => {
  const page = await ready(ctx); const spec = (await info(page)).spec;
  assert((await info(page)).solutionButtonHidden, '初始参考按钮应隐藏');
  for (let i = 0; i < spec.hints.length; i += 1) {
    await click(page, 'hint'); const result = await info(page);
    assert(result.hints.length === i + 1 && result.hints[i] === spec.hints[i], '提示内容或数量错误');
    assert(result.solutionButtonHidden === (i + 1 < spec.hints.length), '提示解锁时机错误');
  }
  assert((await info(page)).solutionHidden, '解锁按钮不应自动展开答案');
  await click(page, 'solution-btn');
  const readOnly = await ev(page, () => {
    const code = document.querySelector('.lab-solution code');
    return !code.isContentEditable && code.children.length === 0 && code.textContent === JSON.parse(document.querySelector('.lab-spec').textContent).solution;
  });
  assert(readOnly && !(await info(page)).solutionHidden, '参考写法未以只读纯文本呈现');
});
test('E2 两次检查失败解锁参考写法', async (ctx) => {
  const page = await ready(ctx); await hook(page, 'setCode', 'print("错")\n');
  await runButton(page, 'check'); assert((await info(page)).solutionButtonHidden, '一次失败就解锁');
  await runButton(page, 'check'); assert(!(await info(page)).solutionButtonHidden, '两次失败未解锁');
  await click(page, 'solution-btn'); assert(!(await info(page)).solutionHidden, '解锁后无法展开');
});

test('F1 窄屏零依赖请求', async (ctx) => {
  const page = await newPage(ctx); await click(page, 'start'); await waitState(page, 'narrow');
  const result = await info(page);
  assert(result.note === '屏幕太窄，请在电脑上或把窗口拉宽后练习' && result.startHidden && !result.previewHidden, '窄屏退路错误');
  assert(!ctx.diag.requests.some((r) => /\/vendor\/|lab-worker\.js|lab-runner\.py|lab-config\.json/.test(r.path)), '窄屏请求运行依赖');
  await capture(ctx, page, 'narrow');
}, {width: 500});
test('F2 文件协议离线退路', async (ctx) => {
  const page = await newPage(ctx); await click(page, 'start'); await waitState(page, 'offline');
  const result = await info(page);
  assert(result.note === '离线打开不能运行代码，请用在线地址练习' && result.startHidden && !result.previewHidden, '离线退路错误');
  assert(!ctx.diag.requests.some((r) => /vendor|pyodide|lab-worker/.test(r.path)), '文件协议加载了运行依赖');
}, {offline: true});
test('F3 Pyodide 拦截失败与重试', async (ctx) => {
  ctx.expected.set('/assets/vendor/pyodide/pyodide.js', '本用例主动阻断 Pyodide');
  const page = await newPage(ctx); await click(page, 'start'); await waitState(page, 'error', 60000);
  const result = await info(page);
  assert(result.note.includes('加载失败：') && result.startText === '重试' && !result.startHidden && !result.previewHidden, '失败后不能重试');
  await capture(ctx, page, 'load-error');
  ctx.options.blocked = [];
  await page._client().send('Network.setBlockedURLs', {urls: []});
  await Promise.allSettled(ctx.sessions.map((session) => session.send('Network.setBlockedURLs', {urls: []})));
  await begin(page);
  assert((await info(page)).state === 'ready', '解除阻断后重试失败');
}, {blocked: ['*vendor/pyodide/pyodide.js*']});

test('G 深浅主题即时切换', async (ctx) => {
  const page = await newPage(ctx); await ev(page, () => document.documentElement.setAttribute('data-theme', 'dark')); await begin(page);
  assert((await info(page)).classes.includes('vs-dark'), '深色主题错误'); await capture(ctx, page, 'dark');
  await ev(page, () => document.documentElement.setAttribute('data-theme', 'light'));
  await waitFor(async () => /\bvs\b/.test((await info(page)).classes) && !(await info(page)).classes.includes('vs-dark'), 3000, '浅色主题切换');
  await capture(ctx, page, 'light');
});

test('H0 原版 CLI 切换配置', async (ctx) => {
  execFileSync(python, [path.join(toolsRoot, 'set_labs.py'), '--site-dir', ctx.site, '--no-yaml', '--paste', 'block'], {encoding: 'utf8', stdio: 'pipe', env: Object.assign({}, process.env, {PYTHONDONTWRITEBYTECODE: '1'})});
  assert(JSON.parse(await fs.readFile(path.join(ctx.site, 'assets/lab-config.json'))).block_paste === true, 'CLI 未切换 block');
  await config(ctx, false);
});
test('H1 默认允许 Ctrl+V 且未安装防线', async (ctx) => {
  const page = await ready(ctx); await hook(page, 'setCode', ''); await paste(page, '粘贴成功');
  await waitFor(async () => (await hook(page, 'getCode')).includes('粘贴成功'), 3000, '真实 Ctrl+V');
  const result = await info(page);
  assert(result.guard === 'allow' && result.probe.guardInstalls === 0 && result.probe.guardListeners === 0 && result.toastHidden && result.toast === '', '允许状态安装防线或显示提示');
});
test('H2 允许拖放文字与右键菜单', async (ctx) => {
  const page = await ready(ctx); await hook(page, 'setCode', ''); await drag(page, '拖放成功');
  await waitFor(async () => (await hook(page, 'getCode')).includes('拖放成功'), 3000, '允许拖放文字');
  assert(await contextMenu(page), '允许状态右键菜单不可见'); assert((await info(page)).toastHidden, '允许状态出现提示条');
});
for (const variant of ['ctrl', 'command', 'shift', 'drop', 'context']) test('H3 阻断 ' + variant, async (ctx) => {
  await config(ctx, true); const page = await ready(ctx); await hook(page, 'setCode', '手敲原文');
  const initial = await info(page); assert(initial.guard === 'block' && initial.probe.guardInstalls === 1 && initial.probe.guardListeners > 0, 'block 未安装防线');
  if (variant === 'drop') await drag(page, '不应进入');
  else if (variant === 'context') assert(!(await contextMenu(page)), '阻断状态出现右键菜单');
  else await paste(page, '不应进入', variant);
  const result = await info(page);
  assert(result.code === '手敲原文' && !result.toastHidden && result.toast === '这里需要手敲输入', '防线未拦截或未提示：' + JSON.stringify({code: result.code, toastHidden: result.toastHidden}));
  const started = Date.now(); await waitFor(async () => (await info(page)).toastHidden, 3000, '约两秒隐藏提示');
  assert(Date.now() - started >= 1600, '提示过早消失');
});
test('H4 block 逐字输入与撤销重做', async (ctx) => {
  await config(ctx, true); const page = await ready(ctx); await typeText(page, 'abc');
  await key(page, 'z', 'KeyZ', 2, 'undo'); assert(await hook(page, 'getCode') !== 'abc', '撤销无效');
  await key(page, 'y', 'KeyY', 2, 'redo'); assert(await hook(page, 'getCode') === 'abc', '重做无效');
  assert((await info(page)).toastHidden, '正常输入或撤销重做出现防线提示');
});
test('H5 block 真实 CDP 输入法组词', async (ctx) => {
  await config(ctx, true); const page = await ready(ctx); await hook(page, 'setCode', ''); await focus(page);
  const client = page._client();
  await client.send('Input.imeSetComposition', {text: '中文组词', selectionStart: 4, selectionEnd: 4});
  assert((await hook(page, 'getCode')).includes('中文组词'), '组词文本未进入编辑器');
  await client.send('Input.insertText', {text: '中文组词'});
  assert(await hook(page, 'getCode') === '中文组词' && (await info(page)).toastHidden, '提交组词被误拦');
});
test('H6 block 编辑器复制剪切及输出复制', async (ctx) => {
  await config(ctx, true); const page = await ready(ctx); await typeText(page, '手敲代码');
  await clipboard(page, '剪贴板旧值'); await selectAll(page); await key(page, 'c', 'KeyC', 2, 'copy');
  assert(await ev(page, () => navigator.clipboard.readText()) === '手敲代码', '编辑器复制被误拦');
  await key(page, 'x', 'KeyX', 2, 'cut');
  await waitFor(async () => await hook(page, 'getCode') === '', 3000, '编辑器剪切');
  assert(await ev(page, () => navigator.clipboard.readText()) === '手敲代码', '剪切未更新系统剪贴板');
  await typeText(page, 'print("可复制输出")'); await runButton(page);
  await ev(page, () => {
    const out = document.querySelector('.lab-out'); out.setAttribute('tabindex', '0'); out.focus();
    const range = document.createRange(); range.selectNodeContents(out); const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
  });
  await key(page, 'c', 'KeyC', 2, 'copy');
  assert((await ev(page, () => navigator.clipboard.readText())).trim() === '可复制输出', '输出区选中复制失败');
  assert((await info(page)).toastHidden, '正常复制剪切出现提示条');
});
test('H7 block 起始预览与提示禁止选择复制', async (ctx) => {
  await config(ctx, true); const page = await ready(ctx); await click(page, 'hint');
  const results = await ev(page, () => ['.lab-starter', '.lab-hints'].map((selector) => {
    const node = document.querySelector(selector);
    const copy = new ClipboardEvent('copy', {bubbles: true, cancelable: true}); node.dispatchEvent(copy);
    return {selector, userSelect: getComputedStyle(node).userSelect, blocked: copy.defaultPrevented};
  }));
  assert(results.every((r) => r.userSelect === 'none' && r.blocked), '禁止选择或复制防线缺失：' + JSON.stringify(results));
});
test('H8 不重建切 block 再切 allow', async (ctx) => {
  const page = await ready(ctx); assert((await info(page)).guard === 'allow', '默认配置不是 allow');
  await config(ctx, true); await reload(ctx, page); await begin(page); assert((await info(page)).guard === 'block', '新开始未读取 block');
  await config(ctx, false); await reload(ctx, page); await begin(page); await hook(page, 'setCode', ''); await paste(page, '恢复粘贴', 'command');
  await waitFor(async () => (await hook(page, 'getCode')).includes('恢复粘贴'), 3000, '切回 allow 粘贴');
  assert((await info(page)).guard === 'allow' && (await info(page)).probe.guardListeners === 0, '切回 allow 仍安装防线');
});
for (const [name, value] of [['缺失', null], ['非法 JSON', '{broken'], ['非布尔字段', '{"block_paste":"true"}']]) test('H9 配置退路 ' + name, async (ctx) => {
  const configFile = path.join(ctx.site, 'assets/lab-config.json');
  if (value === null) { ctx.expected.set('/assets/lab-config.json', '本用例主动删除配置'); await fs.rm(configFile); }
  else await fs.writeFile(configFile, value);
  const page = await ready(ctx); await hook(page, 'setCode', ''); await paste(page, '容错粘贴', 'command');
  await waitFor(async () => (await hook(page, 'getCode')).includes('容错粘贴'), 3000, '配置容错粘贴');
  const result = await info(page); assert(result.guard === 'allow' && result.probe.guardInstalls === 0 && result.toastHidden && result.note === '', '配置失败未回退允许或显示报错');
});

async function run() {
  const options = parseArgs(process.argv.slice(2));
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'ebook-lab-e2e-'));
  const site = path.join(temporary, 'site');
  const results = [], diagnostics = [], shots = [], runtime = {};
  const startedAt = new Date().toISOString();
  let server, browser;
  function redact(value) {
    let safe = String(value);
    for (const [from, to] of [[temporary, '<临时目录>'], [workspace, '<工作区>'], [server && server.origin, '<临时站点>'],
      [server && server.authorization, '<临时认证>'], [server && server.password, '<临时认证>']]) if (from) safe = safe.split(from).join(to);
    return safe;
  }
  async function record(name, fn) {
    const started = Date.now(); let error = null;
    try { await fn(); } catch (caught) { error = redact(caught.stack || caught); }
    const result = {name, passed: !error, durationMs: Date.now() - started, error}; results.push(result);
    process.stdout.write((error ? 'FAIL ' : 'PASS ') + name + ' ' + result.durationMs + 'ms' + (error ? ' ' + error.split('\n')[0] : '') + '\n');
  }
  try {
    await fs.cp(options.site, site, {recursive: true});
    await fs.mkdir(path.join(workspace, 'out/shots'), {recursive: true});
    // Remove screenshots from previous runs so that this report only describes this run.
    for (const file of await fs.readdir(path.join(workspace, 'out/shots'))) if (file.endsWith('.png')) await fs.rm(path.join(workspace, 'out/shots', file));
    server = await startServer(site, temporary);
    browser = await renderer.openBrowser('chrome', {browserExecutable: chrome, chromiumOptions: {gl: 'swangle', ignoreCertificateErrors: true}, logLevel: 'error'});
    for (const entry of tests) {
      const diag = {name: entry.name, requests: [], responses: [], loadingFailures: [], logs: [], exceptions: [], csp: []};
      const ctx = {browser, server, site, runtime, options: entry.options, diag, shots, pages: [], workerTasks: [], sessions: [], expected: new Map(), notes: [], closing: false};
      await fs.writeFile(path.join(site, 'assets/lab-config.json'), '{"block_paste":false}\n');
      await record(entry.name, async () => {
        let timer;
        try {
          await Promise.race([entry.fn(ctx), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('用例总超时（100 秒）')), 100000); })]);
        } catch (error) {
          for (const page of ctx.pages) {
            await capture(ctx, page, 'fail-' + String(results.length + 1)).catch(() => {});
            try { diag.failureState = await info(page); } catch (_) {}
          }
          if (error.stderr) {
            const stderr = redact(String(error.stderr).trim());
            throw new Error('原版 CLI 退出失败：' + stderr.split('\n').pop() + '\n' + stderr);
          }
          throw error;
        } finally {
          clearTimeout(timer); ctx.closing = true;
          for (const page of ctx.pages) {
            try { diag.csp.push(...await ev(page, () => window.__E2E.csp)); } catch (_) {}
            await page.close().catch(() => {});
          }
          await Promise.allSettled(ctx.workerTasks);
          diag.notes = Array.from(new Set(ctx.notes)); diagnostics.push(diag);
        }
      });
    }
    await record('I 全程无非预期错误', async () => {
      const unexpected = [];
      for (const diag of diagnostics) {
        for (const response of diag.responses) if (!response.expected) unexpected.push({case: diag.name, response});
        for (const log of diag.logs) if (log.level === 'error' && !log.expected || /content security policy|violat|refused to/i.test(log.text)) unexpected.push({case: diag.name, log});
        for (const failure of diag.loadingFailures) if (!failure.expected) unexpected.push({case: diag.name, failure});
        for (const exception of diag.exceptions) unexpected.push({case: diag.name, exception});
        for (const csp of diag.csp) unexpected.push({case: diag.name, csp});
        for (const request of diag.requests) if (request.path.includes('<站外请求>')) unexpected.push({case: diag.name, request});
      }
      assert(unexpected.length === 0, '发现非预期控制台/CSP/异常/网络错误：' + redact(JSON.stringify(unexpected)));
    });
    await record('J 五类截图齐全', async () => {
      for (const name of ['light', 'dark', 'narrow', 'error', 'passed']) {
        assert(shots.includes('out/shots/' + name + '.png'), '缺少 ' + name + ' 截图');
        const data = await fs.readFile(path.join(workspace, 'out/shots', name + '.png'));
        assert(data.subarray(1, 4).toString() === 'PNG', name + ' 不是 PNG');
        assert(data.readUInt32BE(16) === (name === 'narrow' ? 500 : 1000), name + ' 截图视口宽度错误');
      }
    });
  } catch (error) { await record('初始化', async () => { throw error; }); }
  finally {
    if (browser) await browser.close({silent: true}).catch(() => {});
    if (server) await server.close().catch(() => {});
    await fs.rm(temporary, {recursive: true, force: true});
  }
  const passed = results.filter((result) => result.passed).length, failed = results.length - passed;
  const summary = {runtime, startedAt, finishedAt: new Date().toISOString(), command: 'node tests/labs/e2e/run_e2e.mjs --site ' + path.relative(workspace, options.site), passed, failed, results, screenshots: shots, diagnostics};
  await fs.writeFile(path.join(workspace, 'out/e2e-results.json'), redact(JSON.stringify(summary, null, 2)) + '\n');
  const errors = diagnostics.flatMap((diag) => diag.logs.filter((log) => log.level === 'error' && !log.expected));
  const exceptions = diagnostics.flatMap((diag) => diag.exceptions), csp = diagnostics.flatMap((diag) => diag.csp);
  const expected = diagnostics.flatMap((diag) => diag.responses.filter((r) => r.expected));
  const report = ['# 页内代码练习真实 Chrome 实测', '', '运行时间（UTC）：' + startedAt, '',
    '命令：`' + summary.command + '`', '', 'Node ' + process.version + '；' + (runtime.chrome || 'Chrome 未启动') + '；真实 Chrome headless shell；原站点的临时副本；HTTPS + Basic Auth + 原版严格 CSP。临时服务、证书、认证和站点副本已清理。', '',
    `汇总：${passed} 通过，${failed} 失败。失败保持真实断言，详见 BUGS.md；完整诊断见 e2e-results.json。`, '',
    '| 用例 | 结果 | 耗时 | 备注 |', '|---|---|---:|---|',
    ...results.map((r) => `| ${r.name} | ${r.passed ? 'PASS' : 'FAIL'} | ${r.durationMs} ms | ${r.error ? r.error.split('\n')[0].replace(/\|/g, '\\|') : ''} |`), '',
    '## 截图', '', ...shots.map((shot) => '- `' + shot + '`'), '',
    '## 错误采集与预期资源缺失', '', `非预期控制台错误 ${errors.length}；未捕获异常 ${exceptions.length}；页面 CSP 违规 ${csp.length}；预期 HTTP 错误 ${expected.length}。`, '',
    '只豁免提供站点缺失的十张章内截图及一段视频、F3 主动阻断 Pyodide、H9 主动删除配置的对应网络错误；不按 pyodide 等关键字笼统忽略异常。缺失媒体在各用例中原样请求，未补造媒体。', '',
    '## 覆盖边界及解释', '',
    '输入法使用真实 Input.imeSetComposition 创建并提交组词；未测操作系统候选窗的候选选择（无头浏览器没有该窗口）。拖放采用真实 Input.dispatchDragEvent；粘贴、复制、剪切使用真实系统剪贴板及 CDP 编辑命令。', '',
    '原版 set_labs.py --no-yaml 的可执行性单独严格验证；若因交付缺少 labs.py 而失败，浏览器开关用等价 JSON 写入继续验证，并在诊断中标明。没有修改原站点或加载 out/patches 中的候选修复。', '',
    '截图为当前无头环境的原始渲染；系统缺少中文回退字体，部分中文显示为方框。DOM 中文文本均另有直接断言；没有安装字体或修改页面字体。', '',
    '各用例总超时 100 秒，状态/草稿/提示消失用条件轮询；没有用固定睡眠判定完成。浏览器用例失败自动截图；CLI 用例无页面，记录完整错误；其余用例继续执行。', ''].join('\n');
  await fs.writeFile(path.join(workspace, 'out/E2E-RESULT.md'), report);
  process.stdout.write(`\n汇总：${passed} 通过，${failed} 失败\n`);
  process.exitCode = failed ? 1 : 0;
}
run().catch((error) => { process.stderr.write(String(error.message || error) + '\n'); process.exitCode = 1; });
