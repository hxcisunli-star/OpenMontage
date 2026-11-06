import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import LabCore from '../../docs/whiteboard/ebook/lab-core.js';

class Element {
  constructor(tag = 'div', attrs = {}) {
    this.tagName = tag.toUpperCase();
    this.attrs = { ...attrs };
    this.children = [];
    this.firstChild = null;
    this.listeners = new Map();
    this.hidden = false;
    this.disabled = false;
    this.textContent = '';
    this.className = '';
  }
  getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  addEventListener(name, fn) { this.listeners.set(name, fn); }
  dispatch(name, event = {}) { const fn = this.listeners.get(name); if (fn) fn({ target: this, ...event }); }
  appendChild(child) { this.children.push(child); this.firstChild = this.children[0] || null; return child; }
  removeChild(child) { this.children = this.children.filter((item) => item !== child); this.firstChild = this.children[0] || null; }
  querySelector(selector) {
    if (selector === 'code' && this.code) return this.code;
    return this.lookup && this.lookup[selector] ? this.lookup[selector] : null;
  }
}

function makePage({ protocol = 'https:', width = 900, config = null, timeout = 1, silentWorker = false, initTimeout = 0 } = {}) {
  const section = new Element('section', { 'data-lab-id': 'demo', 'data-assets-root': '/assets/' });
  const elements = {};
  const add = (key, selector, attrs = {}) => {
    const item = new Element('div', attrs);
    elements[key] = item;
    selectors[selector] = item;
    return item;
  };
  const selectors = {};
  const spec = add('spec', '.lab-spec');
  spec.textContent = JSON.stringify({ id: 'demo', starter: 'print(1)', prelude: '', tests: [{ id: 'ok', name: 'ok', code: 'assert True' }], hints: ['h'], solution: 'print(2)', timeout, seed: null, optional: true });
  add('preview', '.lab-preview');
  add('work', '.lab-work');
  add('editor', '.lab-editor');
  add('note', '.lab-note');
  add('status', '.lab-status');
  add('stdout', '.lab-out');
  add('error', '.lab-err');
  add('checks', '.lab-checks');
  add('hints', '.lab-hints');
  const solution = add('solution', '.lab-solution');
  const code = new Element('code'); solution.code = code;
  add('done', '.lab-done');
  for (const action of ['start', 'run', 'check', 'stop', 'reset', 'hint', 'solution']) add(action, `[data-action="${action}"]`);
  section.querySelector = (selector) => selectors[selector] || null;
  const document = {
    readyState: 'complete',
    documentElement: new Element('html'),
    head: new Element('head'),
    querySelectorAll: () => [section],
    getElementById: () => null,
    createElement: (tag) => new Element(tag),
    createTextNode: (value) => ({ textContent: value })
  };
  class FakeWorker {
    static all = [];
    constructor(url) { this.url = url; this.messages = []; this.terminated = false; FakeWorker.all.push(this); }
    postMessage(message) {
      this.messages.push(message);
      if (message.type === 'init' && !silentWorker) setTimeout(() => { if (this.onmessage) this.onmessage({ data: { type: 'init-ok', reqId: message.reqId, pythonVersion: '3.12.0' } }); }, 0);
    }
    terminate() { this.terminated = true; }
  }
  const storage = new Map();
  const calls = { fetch: 0, installs: 0 };
  const sandbox = {
    document, location: { protocol, href: `${protocol}//example.test/book.html` }, innerWidth: width,
    WebAssembly: {}, Worker: FakeWorker, URL, Map, Promise, Date, Math, JSON, isFinite,
    setTimeout, clearTimeout, console, localStorage: { getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v), removeItem: (k) => storage.delete(k) },
    LabCore,
    LabGuard: { install: () => { calls.installs += 1; return { dispose() {} }; } },
    monaco: {
      KeyMod: { CtrlCmd: 1 }, KeyCode: { Enter: 2 },
      editor: {
        create: () => ({ value: '', getValue() { return this.value; }, setValue(v) { this.value = v; }, getModel() { return {}; }, onDidChangeModelContent() {}, addCommand() {} }),
        setTheme() {}, setModelMarkers() {}
      }
    },
    fetch: () => { calls.fetch += 1; return config instanceof Error ? Promise.reject(config) : Promise.resolve({ ok: true, json: () => Promise.resolve(config == null ? {} : config) }); }
  };
  if (initTimeout) sandbox.__LAB_INIT_TIMEOUT_MS = initTimeout;
  sandbox.globalThis = sandbox;
  vm.runInNewContext(fs.readFileSync(new URL('../../docs/whiteboard/ebook/lab.js', import.meta.url), 'utf8'), sandbox);
  return { sandbox, section, elements, calls, FakeWorker, instance: sandbox.__EBOOK_LABS__.instances.get('demo') };
}

test('does no network work before start and treats failed config as allow', async () => {
  const page = makePage({ config: new Error('offline') });
  assert.equal(page.calls.fetch, 0);
  assert.equal(page.FakeWorker.all.length, 0);
  page.elements.start.dispatch('click');
  await page.instance.whenState('ready', 1000);
  assert.equal(page.calls.fetch, 1);
  assert.equal(page.section.getAttribute('data-paste-guard'), 'allow');
  assert.equal(page.calls.installs, 0);
});

test('blocking configuration installs the guard and marks the section', async () => {
  const page = makePage({ config: { block_paste: true } });
  page.elements.start.dispatch('click');
  await page.instance.whenState('ready', 1000);
  assert.equal(page.section.getAttribute('data-paste-guard'), 'block');
  assert.equal(page.calls.installs, 1);
});

test('timeout terminates the worker and the next run builds a new one', async () => {
  const page = makePage({ config: {} });
  page.elements.start.dispatch('click');
  await page.instance.whenState('ready', 1000);
  await page.instance.run('run');
  assert.equal(page.FakeWorker.all.length, 1);
  await new Promise((resolve) => setTimeout(resolve, 1100));
  assert.match(page.elements.status.textContent, /已超时/);
  page.instance.run('run');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(page.FakeWorker.all.length, 2);
  const old = page.FakeWorker.all[0];
  if (old.onmessage) old.onmessage({ data: { type: 'run-result', reqId: 'old', stdout: '迟到', error: null, checks: [] } });
  assert.equal(page.elements.stdout.textContent, '');
  page.instance.stop();
});

test('offline and narrow pages do not fetch or create workers; reset is confirmed twice', async () => {
  const offline = makePage({ protocol: 'file:', config: { block_paste: true } });
  offline.elements.start.dispatch('click');
  assert.equal(offline.calls.fetch, 0);
  assert.equal(offline.FakeWorker.all.length, 0);
  const narrow = makePage({ width: 500, config: { block_paste: true } });
  narrow.elements.start.dispatch('click');
  assert.equal(narrow.calls.fetch, 0);
  assert.equal(narrow.FakeWorker.all.length, 0);
  const page = makePage({ config: {} });
  page.elements.start.dispatch('click');
  await page.instance.whenState('ready', 1000);
  page.instance.setCode('changed');
  page.instance.reset(false);
  assert.equal(page.elements.reset.textContent, '确认重置？');
  page.instance.reset(false);
  assert.equal(page.instance.getCode(), 'print(1)');
});

test('a start-up that never answers ends in an error with a diagnosis, shows the steps reached, and the preview comes back', async () => {
  const page = makePage({ config: {}, silentWorker: true, initTimeout: 60 });
  page.elements.start.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 15));
  assert.equal(page.elements.preview.hidden, true);                     // no start button sitting on top of the toolbar while loading
  const worker = page.FakeWorker.all[0];
  worker.onmessage({ data: { type: 'init-stage', reqId: worker.messages[0].reqId, stage: 'loadPyodide' } });
  assert.match(page.elements.status.textContent, /编译并启动 Python 内核/);
  await page.instance.whenState('error', 1000);
  assert.match(page.elements.note.textContent, /启动 Python 超过/);
  assert.match(page.elements.note.textContent, /步骤：loadPyodide/);
  assert.match(page.elements.note.textContent, /WebAssembly/);
  assert.equal(page.elements.preview.hidden, false);
  assert.equal(worker.terminated, true);
});
