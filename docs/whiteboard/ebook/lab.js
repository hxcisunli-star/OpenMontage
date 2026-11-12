(function (root) {
  'use strict';

  var doc = root.document;
  if (!doc) return;
  var Core = root.LabCore || {};
  var Guard = root.LabGuard || {};
  var page = {
    instances: new Map(),
    monacoPromise: null,
    monacoRoot: null,
    worker: null,
    workerRoot: null,
    initPromise: null,
    initPending: null,
    queue: [],
    active: null,
    sequence: 0,
    themeObserver: null
  };

  function text(value) {
    return typeof value === 'string' ? value : (value == null ? '' : String(value));
  }

  function assetUrl(assetRoot, name) {
    var base = text(assetRoot);
    var href = root.location && root.location.href ? root.location.href : (doc.baseURI || 'file:///ebook/');
    return new URL(base + name, href).href;
  }

  function nextId(prefix) {
    page.sequence += 1;
    return prefix + '-' + String(page.sequence);
  }

  function listen(element, event, handler, options) {
    if (element && typeof element.addEventListener === 'function') element.addEventListener(event, handler, options);
  }

  function find(section, selector, id) {
    var element = null;
    try { element = section.querySelector(selector); } catch (e) {}
    if (!element && doc.getElementById && id) element = doc.getElementById(id);
    return element;
  }

  function setHidden(element, value) {
    if (element) element.hidden = !!value;
  }

  function clearChildren(element) {
    if (!element) return;
    while (element.firstChild) element.removeChild(element.firstChild);
  }

  function pageEnvironment() {
    var location = root.location || {};
    return {
      protocol: text(location.protocol),
      innerWidth: typeof root.innerWidth === 'number' ? root.innerWidth : 1000,
      hasWorker: typeof root.Worker === 'function',
      hasWasm: typeof root.WebAssembly !== 'undefined'
    };
  }

  function themeName() {
    var html = doc.documentElement;
    var selected = html && html.getAttribute ? html.getAttribute('data-theme') : null;
    if (selected === 'dark') return 'vs-dark';
    if (selected === 'light') return 'vs';
    try {
      if (root.matchMedia && root.matchMedia('(prefers-color-scheme: dark)').matches) return 'vs-dark';
    } catch (e) {}
    return 'vs';
  }

  function applyTheme() {
    if (root.monaco && root.monaco.editor && typeof root.monaco.editor.setTheme === 'function') root.monaco.editor.setTheme(themeName());
  }

  function watchTheme() {
    if (page.themeObserver || typeof root.MutationObserver !== 'function' || !doc.documentElement) return;
    page.themeObserver = new root.MutationObserver(function () { applyTheme(); });
    page.themeObserver.observe(doc.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  }

  function appendMonacoCss(assetRoot) {
    if (!doc.createElement) return;
    var existing = null;
    try { existing = doc.querySelector('link[data-ebook-monaco]'); } catch (e) {}
    if (existing) return;
    var link = doc.createElement('link');
    link.setAttribute('rel', 'stylesheet');
    link.setAttribute('data-ebook-monaco', '1');
    link.setAttribute('href', assetUrl(assetRoot, 'vendor/monaco/vs/editor/editor.main.css'));
    (doc.head || doc.documentElement).appendChild(link);
  }

  function configureAmd(assetRoot) {
    var amd = root.require;
    if (typeof amd !== 'function' || typeof amd.config !== 'function') return false;
    amd.config({ paths: { vs: assetUrl(assetRoot, 'vendor/monaco/vs') } });
    return true;
  }

  function requestMonaco(assetRoot) {
    return new Promise(function (resolve, reject) {
      var amd = root.require;
      if (typeof amd !== 'function') {
        reject(new Error('Monaco 加载器不可用'));
        return;
      }
      try {
        if (typeof amd.config === 'function') amd.config({ paths: { vs: assetUrl(assetRoot, 'vendor/monaco/vs') } });
        amd(['vs/editor/editor.main'], function (loadedMonaco) {
          if (loadedMonaco && loadedMonaco.editor) { root.monaco = loadedMonaco; resolve(loadedMonaco); }
          else if (root.monaco) resolve(root.monaco);
          else reject(new Error('编辑器加载失败'));
        }, reject);
      } catch (error) {
        reject(error);
      }
    });
  }

  function loadMonaco(assetRoot) {
    root.MonacoEnvironment = {
      getWorkerUrl: function () { return assetUrl(assetRoot, 'vendor/monaco/vs/base/worker/workerMain.js'); }
    };
    if (root.monaco && root.monaco.editor) {
      appendMonacoCss(assetRoot);
      configureAmd(assetRoot);
      return Promise.resolve(root.monaco);
    }
    if (page.monacoPromise) return page.monacoPromise;
    page.monacoRoot = assetRoot;
    page.monacoPromise = new Promise(function (resolve, reject) {
      appendMonacoCss(assetRoot);
      if (configureAmd(assetRoot)) {
        requestMonaco(assetRoot).then(resolve, reject);
        return;
      }
      if (!doc.createElement) {
        reject(new Error('无法创建编辑器加载器'));
        return;
      }
      var script = doc.createElement('script');
      script.setAttribute('src', assetUrl(assetRoot, 'vendor/monaco/vs/loader.js'));
      script.onload = function () { requestMonaco(assetRoot).then(resolve, reject); };
      script.onerror = function () { reject(new Error('编辑器加载失败')); };
      (doc.head || doc.documentElement).appendChild(script);
    });
    page.monacoPromise.catch(function () { page.monacoPromise = null; });
    return page.monacoPromise;
  }

  var INIT_TIMEOUT_MS = (typeof root.__LAB_INIT_TIMEOUT_MS === 'number' && root.__LAB_INIT_TIMEOUT_MS > 0) ? root.__LAB_INIT_TIMEOUT_MS : 90000;   // the override is for tests
  var STAGE_TEXT = { importScripts: '读取运行时', loadPyodide: '编译并启动 Python 内核（首次要几秒）', runner: '载入运行器' };

  function clearInitTimer() {
    if (page.initTimer) { root.clearTimeout(page.initTimer); page.initTimer = null; }
  }

  // what a learner can copy into a message when the start-up hangs in their browser
  function diagnostics() {
    var parts = [];
    parts.push('步骤：' + (page.stages && page.stages.length ? page.stages.join(' > ') : '没有收到任何步骤'));
    try { parts.push('浏览器：' + text(root.navigator && root.navigator.userAgent).replace(/^Mozilla\/5\.0 /, '').slice(0, 130)); } catch (e) {}
    parts.push('WebAssembly：' + (root.WebAssembly ? '有' : '无'));
    parts.push('安全上下文：' + (root.isSecureContext ? '是' : '否'));
    return parts.join('；');
  }

  function resetWorker() {
    clearInitTimer();
    var worker = page.worker;
    page.worker = null;
    page.workerRoot = null;
    page.initPromise = null;
    page.initPending = null;
    if (worker) {
      try { worker.onmessage = null; worker.onerror = null; } catch (e) {}
      try { worker.terminate(); } catch (e2) {}
    }
  }

  function failInit(error) {
    clearInitTimer();
    var pending = page.initPending;
    page.initPending = null;
    page.initPromise = null;
    if (pending) pending.reject(error instanceof Error ? error : new Error(text(error)));
  }

  function receiveWorkerMessage(message) {
    var data = message && message.data ? message.data : message;
    if (!data || typeof data !== 'object') return;
    if (data.type === 'init-stage') {
      if (page.initPending && page.initPending.reqId === data.reqId) {
        page.stages.push(text(data.stage));
        if (page.stages.length > 16) page.stages.shift();
        if (typeof page.onStage === 'function') page.onStage(text(data.stage));
      }
      return;
    }
    if (data.type === 'init-ok' || data.type === 'init-error') {
      var init = page.initPending;
      if (!init || init.reqId !== data.reqId) return;
      clearInitTimer();
      page.initPending = null;
      if (data.type === 'init-ok') init.resolve(data);
      else init.reject(new Error(text(data.message) || 'Python 启动失败'));
      return;
    }
    if (data.type !== 'run-result') return;
    var active = page.active;
    if (!active || active.reqId !== data.reqId) return;
    if (active.timer) root.clearTimeout(active.timer);
    page.active = null;
    active.item.resolve(data);
    pumpQueue();
  }

  function ensureWorker(assetRoot) {
    if (page.worker && page.initPromise && page.workerRoot === assetRoot) return page.initPromise;
    if (page.worker) resetWorker();
    if (typeof root.Worker !== 'function') return Promise.reject(new Error('浏览器不支持 Worker'));
    var worker;
    try {
      worker = new root.Worker(assetUrl(assetRoot, 'lab-worker.js'));
    } catch (error) {
      return Promise.reject(error);
    }
    page.worker = worker;
    page.workerRoot = assetRoot;
    page.stages = [];
    worker.onmessage = receiveWorkerMessage;
    if (typeof worker.addEventListener === 'function') worker.addEventListener('message', receiveWorkerMessage);
    worker.onerror = function (event) {
      if (page.worker !== worker) return;
      var message = event && event.message ? event.message : 'Python 启动失败';
      if (page.initPending) failInit(new Error(message + '。诊断：' + diagnostics()));
      else if (page.active) {
        var active = page.active;
        if (active.timer) root.clearTimeout(active.timer);
        page.active = null;
        resetWorker();
        active.item.reject(new Error(message));
        pumpQueue();
      }
    };
    if (typeof worker.addEventListener === 'function') worker.addEventListener('error', worker.onerror);
    var reqId = nextId('init');
    page.initPromise = new Promise(function (resolve, reject) {
      page.initPending = { reqId: reqId, resolve: resolve, reject: reject };
      try {
        worker.postMessage({
          type: 'init',
          reqId: reqId,
          indexURL: assetUrl(assetRoot, 'vendor/pyodide/'),
          runnerURL: assetUrl(assetRoot, 'lab-runner.py')
        });
      } catch (error) {
        failInit(error);
      }
    });
    page.initTimer = root.setTimeout(function () {
      if (page.worker !== worker || !page.initPending) return;
      var failure = new Error('启动 Python 超过 ' + Math.round(INIT_TIMEOUT_MS / 1000) + ' 秒没有响应。诊断：' + diagnostics());
      failInit(failure);
      resetWorker();
    }, INIT_TIMEOUT_MS);
    page.initPromise.catch(function () { if (page.worker === worker) resetWorker(); });
    return page.initPromise;
  }

  function pumpQueue() {
    if (page.active || !page.queue.length) return;
    var item = page.queue.shift();
    var active = { item: item, reqId: null, timer: null };
    page.active = active;
    ensureWorker(item.assetRoot).then(function () {
      if (page.active !== active) return;
      active.reqId = nextId('run');
      try {
        page.worker.postMessage({
          type: 'run',
          reqId: active.reqId,
          mode: item.mode,
          code: item.code,
          prelude: item.prelude,
          tests: item.tests,
          seed: item.seed
        });
        active.timer = root.setTimeout(function () {
          if (page.active !== active) return;
          page.active = null;
          resetWorker();
          item.resolve({ __timeout: true });
          pumpQueue();
        }, item.timeoutMs);
      } catch (error) {
        page.active = null;
        resetWorker();
        item.reject(error);
        pumpQueue();
      }
    }, function (error) {
      if (page.active !== active) return;
      page.active = null;
      resetWorker();
      item.reject(error);
      pumpQueue();
    });
  }

  function enqueue(instance, spec, mode, code) {
    return new Promise(function (resolve, reject) {
      page.queue.push({
        instance: instance,
        assetRoot: instance.assetRoot,
        mode: mode,
        code: code,
        prelude: spec.prelude || '',
        tests: Array.isArray(spec.tests) ? spec.tests : [],
        seed: spec.seed == null ? null : spec.seed,
        timeoutMs: Math.max(1, Number(spec.timeout) || 10) * 1000,
        resolve: resolve,
        reject: reject
      });
      pumpQueue();
    });
  }

  function cancelFor(instance) {
    var kept = [];
    page.queue.forEach(function (item) {
      if (item.instance === instance) item.resolve({ __stopped: true }); else kept.push(item);
    });
    page.queue = kept;
    if (page.active && page.active.item.instance === instance) {
      var active = page.active;
      if (active.timer) root.clearTimeout(active.timer);
      page.active = null;
      resetWorker();
      active.item.resolve({ __stopped: true });
      pumpQueue();
    }
  }

  function makeEditor(instance, monaco) {
    var options = {
      language: 'python',
      fontSize: 15,
      tabSize: 4,
      insertSpaces: true,
      minimap: { enabled: false },
      automaticLayout: true,
      scrollBeyondLastLine: false,
      ariaLabel: 'Python 代码编辑器'
    };
    if (instance.blockPaste) {
      options.contextmenu = false;
      options.dragAndDrop = false;
      options.dropIntoEditor = { enabled: false };
    }
    setHidden(instance.work, false);
    instance.editor = monaco.editor.create(instance.editorEl, options);
    if (instance.editor && typeof instance.editor.onDidChangeModelContent === 'function') {
      instance.editor.onDidChangeModelContent(function () {
        instance.clearMarkers();
      if (!instance.suppressDraft) instance.scheduleDraft();
      });
    }
    if (instance.editor && typeof instance.editor.addCommand === 'function' && monaco.KeyMod && monaco.KeyCode) {
      instance.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, function () { instance.run('run'); });
    }
    if (instance.editor && typeof instance.editor.focus === 'function') instance.editor.focus();      // keyboard users can type right after "开始练习"
    applyTheme();
    watchTheme();
  }

  function LabInstance(section) {
    var self = this;
    this.section = section;
    this.id = text(section.getAttribute && section.getAttribute('data-lab-id'));
    this.assetRoot = text(section.getAttribute && section.getAttribute('data-assets-root'));
    this.state = 'idle';
    this.editor = null;
    this.guard = null;
    this.blockPaste = false;
    this.passed = false;
    this.checkFailures = 0;
    this.shownHints = 0;
    this.resetTimer = null;
    this.toastTimer = null;
    this.draftTimer = null;
    this.suppressDraft = false;
    this.watchers = [];
    this.operation = 0;
    this.spec = { id: this.id, title: '', goal: '', starter: '', prelude: '', tests: [], hints: [], solution: '', timeout: 10, seed: null, optional: true };
    this.specEl = find(section, '.lab-spec');
    if (this.specEl) {
      try {
        var parsed = JSON.parse(this.specEl.textContent || '');
        if (parsed && typeof parsed === 'object') this.spec = parsed;
      } catch (e) {}
    }
    this.spec.id = this.id || this.spec.id || '';
    this.spec.starter = typeof this.spec.starter === 'string' ? this.spec.starter : '';
    this.spec.hints = Array.isArray(this.spec.hints) ? this.spec.hints : [];
    this.spec.solution = typeof this.spec.solution === 'string' ? this.spec.solution : '';
    this.spec.timeout = Number(this.spec.timeout) >= 1 ? Number(this.spec.timeout) : 10;
    this.preview = find(section, '.lab-preview');
    this.work = find(section, '.lab-work');
    this.editorEl = find(section, '.lab-editor');
    this.note = find(section, '.lab-note');
    this.status = find(section, '.lab-status');
    this.stdout = find(section, '.lab-out');
    this.error = find(section, '.lab-err');
    this.checks = find(section, '.lab-checks');
    this.hintsEl = find(section, '.lab-hints');
    this.solution = find(section, '.lab-solution');
    this.solutionCode = this.solution ? this.solution.querySelector('code') : null;
    this.done = find(section, '.lab-done');
    this.startButton = find(section, '[data-action="start"]', 'lab-' + this.id + '-start');
    this.runButton = find(section, '[data-action="run"]', 'lab-' + this.id + '-run');
    this.checkButton = find(section, '[data-action="check"]', 'lab-' + this.id + '-check');
    this.stopButton = find(section, '[data-action="stop"]', 'lab-' + this.id + '-stop');
    this.resetButton = find(section, '[data-action="reset"]', 'lab-' + this.id + '-reset');
    this.hintButton = find(section, '[data-action="hint"]', 'lab-' + this.id + '-hint');
    this.solutionButton = find(section, '[data-action="solution"]', 'lab-' + this.id + '-solution-btn');
    this.bind();
    section.setAttribute('data-lab-state', 'idle');
    section.setAttribute('data-paste-guard', 'allow');

    this.setState = function (state) {
      self.state = state;
      section.setAttribute('data-lab-state', state);
      var pending = self.watchers.slice();
      self.watchers = [];
      pending.forEach(function (watch) {
        if (watch.timer) root.clearTimeout(watch.timer);
        if (state === watch.state) watch.resolve(state); else self.watchers.push(watch);
      });
    };
    this.getState = function () { return self.state; };
    this.getCode = function () {
      if (self.editor && typeof self.editor.getValue === 'function') return self.editor.getValue();
      return self.spec.starter;
    };
    this.setCode = function (value) {
      var code = text(value);
      if (self.editor && typeof self.editor.setValue === 'function') self.editor.setValue(code);
      self.scheduleDraft();
    };
    this.whenState = function (state, timeoutMs) {
      if (self.state === state) return Promise.resolve(state);
      return new Promise(function (resolve, reject) {
        var watch = { state: state, resolve: resolve, timer: null };
        if (typeof timeoutMs === 'number' && timeoutMs >= 0) watch.timer = root.setTimeout(function () {
          var index = self.watchers.indexOf(watch);
          if (index >= 0) self.watchers.splice(index, 1);
          reject(new Error('等待状态超时'));
        }, timeoutMs);
        self.watchers.push(watch);
      });
    };
    this.showToast = function () {
      var toast = find(section, '.lab-toast');
      if (!toast) return;
      toast.textContent = '这里需要手敲输入';
      toast.hidden = false;
      if (self.toastTimer) root.clearTimeout(self.toastTimer);
      self.toastTimer = root.setTimeout(function () { toast.hidden = true; }, 2000);
    };
    this.clearMarkers = function () {
      if (self.editor && typeof self.editor.getModel === 'function' && root.monaco && root.monaco.editor && typeof root.monaco.editor.setModelMarkers === 'function') {
        var model = self.editor.getModel();
        if (model) root.monaco.editor.setModelMarkers(model, 'ebook-lab', []);
      }
    };
    this.scheduleDraft = function () {
      if (self.draftTimer) root.clearTimeout(self.draftTimer);
      self.draftTimer = root.setTimeout(function () {
        try {
          if (root.localStorage && typeof root.localStorage.setItem === 'function') root.localStorage.setItem(Core.draftKey(self.id), Core.serializeDraft({ starterHash: Core.hashString(self.spec.starter), code: self.getCode(), passed: self.passed, updatedAt: Date.now() }));
        } catch (e) {}
      }, 500);
    };
  }

  LabInstance.prototype.bind = function () {
    var self = this;
    listen(this.startButton, 'click', function () { self.begin(); });
    listen(this.runButton, 'click', function () { self.run('run'); });
    listen(this.checkButton, 'click', function () { self.run('check'); });
    listen(this.stopButton, 'click', function () { self.stop(); });
    listen(this.resetButton, 'click', function () { self.reset(false); });
    listen(this.hintButton, 'click', function () { self.showHint(); });
    listen(this.solutionButton, 'click', function () { self.showSolution(); });
  };

  LabInstance.prototype.setNote = function (message, hidden) {
    if (!this.note) return;
    this.note.textContent = text(message);
    this.note.hidden = !!hidden;
  };

  LabInstance.prototype.refreshConfig = function () {
    var self = this;
    var fetchFn = root.fetch;
    if (typeof fetchFn !== 'function') {
      this.blockPaste = false;
      this.section.setAttribute('data-paste-guard', 'allow');
      this.applyGuard();
      return Promise.resolve({ block_paste: false });
    }
    return Promise.resolve().then(function () {
      return fetchFn(assetUrl(self.assetRoot, 'lab-config.json'), { cache: 'no-store' });
    }).then(function (response) {
      if (response && response.ok === false) throw new Error('配置读取失败');
      return response.json();
    }).catch(function () {
      return { block_paste: false };
    }).then(function (value) {
      var config = Core.normalizeConfig ? Core.normalizeConfig(value) : { block_paste: false };
      self.blockPaste = config.block_paste;
      self.section.setAttribute('data-paste-guard', self.blockPaste ? 'block' : 'allow');
      self.applyGuard();
      return config;
    });
  };

  LabInstance.prototype.applyGuard = function () {
    if (this.guard && typeof this.guard.dispose === 'function') this.guard.dispose();
    this.guard = null;
    if (this.blockPaste && this.editor && Guard && typeof Guard.install === 'function' && this.work) {
      var self = this;
      this.guard = Guard.install(this.work, {
        isBlocked: function () { return self.blockPaste; },
        editor: this.editor,
        onBlocked: function () { self.showToast(); }
      });
    }
  };

  LabInstance.prototype.begin = function () {
    var self = this;
    if (this.state === 'loading' || this.state === 'ready' || this.state === 'running') return this.whenState('ready');
    var env = Core.classifyEnv ? Core.classifyEnv(pageEnvironment()) : 'ok';
    if (env === 'narrow') {
      this.setState('narrow');
      this.setNote('屏幕太窄，请在电脑上或把窗口拉宽后练习', false);
      setHidden(this.startButton, true);
      return Promise.resolve();
    }
    if (env === 'offline') {
      this.setState('offline');
      this.setNote('离线打开不能运行代码，请用在线地址练习', false);
      setHidden(this.startButton, true);
      return Promise.resolve();
    }
    if (env !== 'ok') {
      this.setState('error');
      this.setNote('加载失败：浏览器不支持运行环境', false);
      return Promise.resolve();
    }
    this.setState('loading');
    this.setNote('', true);
    setHidden(this.preview, true);          // the editor will show the code: the preview and its button would sit on top of the toolbar
    setHidden(this.work, false);
    if (this.status) this.status.textContent = '正在加载编辑器 (1/2)…';
    return this.refreshConfig().then(function () {
      return loadMonaco(self.assetRoot);
    }).then(function (monaco) {
      if (self.editor && typeof self.editor.dispose === 'function') self.editor.dispose();
      makeEditor(self, monaco);
      var saved = null;
      try {
        saved = root.localStorage && Core.readDraft ? Core.readDraft(root.localStorage.getItem(Core.draftKey(self.id)), Core.hashString(self.spec.starter)) : null;
      } catch (e) {}
      if (saved) {
        self.passed = saved.passed;
        if (self.editor && typeof self.editor.setValue === 'function') self.editor.setValue(saved.code);
        setHidden(self.done, !self.passed);
      } else if (self.editor && typeof self.editor.setValue === 'function') {
        self.editor.setValue(self.spec.starter);
      }
      self.applyGuard();
      if (self.status) self.status.textContent = '正在启动 Python (2/2)…';
      page.onStage = function (stage) {
        var shown = STAGE_TEXT[stage];
        if (shown && self.status) self.status.textContent = '正在启动 Python (2/2)：' + shown + '…';
      };
      return ensureWorker(self.assetRoot);
    }).then(function () {
      page.onStage = null;
      self.setState('ready');
      self.setNote('', true);
      setHidden(self.preview, true);
      if (self.startButton) { self.startButton.textContent = '重新打开'; self.startButton.hidden = true; }
      if (self.status) self.status.textContent = '';
      self.updateHintButton();
      return self;
    }).catch(function (error) {
      page.onStage = null;
      self.setState('error');
      self.setNote('加载失败：' + (text(error && error.message) || '未知错误'), false);
      setHidden(self.preview, false);
      setHidden(self.work, true);
      if (self.startButton) { self.startButton.textContent = '重试'; self.startButton.hidden = false; }
      if (self.status) self.status.textContent = '';
      return self;
    });
  };

  LabInstance.prototype.clearOutput = function () {
    if (this.stdout) this.stdout.textContent = '';
    if (this.error) { this.error.textContent = ''; this.error.hidden = true; }
    if (this.checks) clearChildren(this.checks);
  };

  LabInstance.prototype.renderChecks = function (checks) {
    var self = this;
    if (!this.checks || !doc.createElement) return;
    clearChildren(this.checks);
    (Core.normalizeChecks ? Core.normalizeChecks(checks) : []).forEach(function (check) {
      var li = doc.createElement('li');
      li.setAttribute('data-check-id', check.id);
      li.setAttribute('data-passed', check.passed ? 'true' : 'false');
      var mark = doc.createElement('span');
      mark.className = 'lab-check-mark';
      mark.textContent = check.passed ? '✓' : '✗';
      li.appendChild(mark);
      var name = doc.createTextNode ? doc.createTextNode(' ' + check.name) : null;
      if (name) li.appendChild(name); else li.textContent = ' ' + check.name;
      if (check.message) {
        var message = doc.createElement('span');
        message.className = 'lab-check-msg';
        message.textContent = '：' + check.message;
        li.appendChild(message);
      }
      self.checks.appendChild(li);
    });
  };

  LabInstance.prototype.renderError = function (error) {
    this.clearMarkers();
    if (!this.error) return;
    if (!error) { this.error.textContent = ''; this.error.hidden = true; return; }
    var markerMessage = text(error.hintZh || error.message || '运行出错');
    var message = markerMessage;
    if (error.lineno != null) message += '\n第 ' + String(error.lineno) + ' 行';
    this.error.textContent = message;
    this.error.hidden = false;
    if (this.editor && typeof this.editor.getModel === 'function' && root.monaco && root.monaco.editor && typeof root.monaco.editor.setModelMarkers === 'function' && error.lineno) {
      var model = this.editor.getModel();
      if (model) root.monaco.editor.setModelMarkers(model, 'ebook-lab', [{ startLineNumber: error.lineno, endLineNumber: error.lineno, startColumn: error.colno || 1, endColumn: (error.colno || 1) + 1, message: markerMessage, severity: root.monaco.MarkerSeverity ? root.monaco.MarkerSeverity.Error : 8 }]);
    }
  };

  LabInstance.prototype.applyResult = function (result, mode) {
    if (!result || result.__stopped || result.__timeout) return;
    if (this.stdout) this.stdout.textContent = text(result.stdout);
    this.renderError(result.error);
    if (mode === 'check') {
      var checks = Core.normalizeChecks ? Core.normalizeChecks(result.checks) : [];
      this.renderChecks(checks);
      if (Core.allChecksPassed && Core.allChecksPassed(checks)) {
        this.passed = true;
        setHidden(this.done, false);
        if (this.status) this.status.textContent = '全部通过 ✓';
      } else {
        this.passed = false;
        this.checkFailures += 1;
        if (this.status) this.status.textContent = '有检查未通过';
      }
      this.updateSolutionButton();
    } else if (this.status) {
      this.status.textContent = result.error ? '运行出错' : '运行完成';
    }
    this.scheduleDraft();
  };

  LabInstance.prototype.run = function (mode) {
    var self = this;
    if (this.state !== 'ready' || !this.editor) return Promise.resolve(null);
    var current = ++this.operation;
    this.setState('running');
    if (this.status) this.status.textContent = '运行中…';
    if (this.runButton) this.runButton.disabled = true;
    if (this.checkButton) this.checkButton.disabled = true;
    setHidden(this.stopButton, false);
    this.clearOutput();
    return enqueue(this, this.spec, mode === 'check' ? 'check' : 'run', this.getCode()).then(function (result) {
      if (current !== self.operation) return result;
      if (result && result.__timeout) {
        self.setState('ready');
        if (self.status) self.status.textContent = Core.timeoutMessage ? Core.timeoutMessage(self.spec.timeout) : '已超时，代码已停止';
      } else if (result && result.__stopped) {
        self.setState('ready');
        if (self.status) self.status.textContent = '已停止';
      } else {
        self.applyResult(result, mode === 'check' ? 'check' : 'run');
        self.setState('ready');
      }
      if (self.runButton) self.runButton.disabled = false;
      if (self.checkButton) self.checkButton.disabled = false;
      setHidden(self.stopButton, true);
      return result;
    }).catch(function (error) {
      if (current !== self.operation) return null;
      self.setState('ready');
      self.renderError({ message: text(error && error.message) || '运行失败' });
      if (self.status) self.status.textContent = '运行出错';
      if (self.runButton) self.runButton.disabled = false;
      if (self.checkButton) self.checkButton.disabled = false;
      setHidden(self.stopButton, true);
      return null;
    });
  };

  LabInstance.prototype.stop = function () {
    if (this.state !== 'running') return;
    this.operation += 1;
    cancelFor(this);
    this.setState('ready');
    if (this.status) this.status.textContent = '已停止';
    if (this.runButton) this.runButton.disabled = false;
    if (this.checkButton) this.checkButton.disabled = false;
    setHidden(this.stopButton, true);
  };

  LabInstance.prototype.check = function () {
    return this.run('check');
  };

  LabInstance.prototype.updateHintButton = function () {
    if (!this.hintButton) return;
    var count = this.spec.hints.length;
    this.hintButton.hidden = count === 0 || this.shownHints >= count;
    this.hintButton.textContent = count ? '提示 (' + String(Math.min(this.shownHints + 1, count)) + '/' + String(count) + ')' : '提示';
    this.updateSolutionButton();
  };

  LabInstance.prototype.updateSolutionButton = function () {
    if (!this.solutionButton) return;
    var unlocked = Core.solutionUnlocked ? Core.solutionUnlocked(this.checkFailures, this.shownHints, this.spec.hints.length) : this.checkFailures >= 2;
    this.solutionButton.hidden = !this.spec.solution || !unlocked;
  };

  LabInstance.prototype.showHint = function () {
    if (this.shownHints >= this.spec.hints.length || !this.hintsEl || !doc.createElement) return;
    var item = doc.createElement('p');
    item.textContent = this.spec.hints[this.shownHints];
    this.hintsEl.appendChild(item);
    this.shownHints += 1;
    this.updateHintButton();
  };

  LabInstance.prototype.showSolution = function () {
    if (!this.solution || !this.spec.solution) return;
    if (this.solutionCode) this.solutionCode.textContent = this.spec.solution;
    this.solution.hidden = false;
  };

  LabInstance.prototype.reset = function (skipConfirm) {
    var self = this;
    if (!skipConfirm && !this.resetArmed) {
      this.resetArmed = true;
      if (this.resetButton) this.resetButton.textContent = '确认重置？';
      if (this.resetTimer) root.clearTimeout(this.resetTimer);
      this.resetTimer = root.setTimeout(function () { self.resetArmed = false; if (self.resetButton) self.resetButton.textContent = '重置'; }, 3000);
      return;
    }
    this.resetArmed = false;
    if (this.resetTimer) root.clearTimeout(this.resetTimer);
    if (this.resetButton) this.resetButton.textContent = '重置';
    if (this.state === 'running') this.stop();
    this.passed = false;
    this.checkFailures = 0;
    this.shownHints = 0;
    if (this.draftTimer) root.clearTimeout(this.draftTimer);
    this.suppressDraft = true;
    if (this.editor && typeof this.editor.setValue === 'function') this.editor.setValue(this.spec.starter);
    this.suppressDraft = false;
    this.clearOutput();
    this.clearMarkers();
    if (this.hintsEl) clearChildren(this.hintsEl);
    if (this.solution) this.solution.hidden = true;
    setHidden(this.done, true);
    try { if (root.localStorage && typeof root.localStorage.removeItem === 'function') root.localStorage.removeItem(Core.draftKey(this.id)); } catch (e) {}
    this.updateHintButton();
    this.setState(this.editor ? 'ready' : 'idle');
  };

  function initialize() {
    var sections = [];
    try { sections = Array.prototype.slice.call(doc.querySelectorAll('section.lab')); } catch (e) {}
    sections.forEach(function (section) {
      var instance = new LabInstance(section);
      page.instances.set(instance.id, instance);
    });
    root.__EBOOK_LABS__ = { instances: page.instances };
  }

  if (doc.readyState === 'loading') listen(doc, 'DOMContentLoaded', initialize); else initialize();
}(typeof globalThis !== 'undefined' ? globalThis : this));
