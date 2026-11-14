import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";
import vm from "node:vm";
import test from "node:test";

const root = existsSync("docs/whiteboard/ebook/lab-worker.js") ? process.cwd() : path.resolve("out");
const require = createRequire(path.join(root, "tests/labs/test_worker_node.mjs"));
const workerSource = readFileSync(path.join(root, "docs/whiteboard/ebook/lab-worker.js"), "utf8");
const runnerPath = path.join(root, "docs/whiteboard/ebook/lab-runner.py");
const runnerSource = readFileSync(runnerPath, "utf8");
const indexURL = pathToFileURL(path.join(root, "vendor/pyodide") + path.sep).href;
const runnerURL = pathToFileURL(runnerPath).href;

function harness(overrides = {}) {
  const replies = [];
  const stages = [];            // "init-stage" progress messages are not replies: the page shows them while Python starts
  const pending = new Map();
  const listeners = new Map();
  const imports = [];
  const fetches = [];
  const worker = {
    importScripts(url) { imports.push(url); },
    async fetch(url) { fetches.push(url); return { ok: true, async text() { return runnerSource; } }; },
    addEventListener(type, handler) { listeners.set(type, handler); },
    postMessage(data) {
      const plain = JSON.parse(JSON.stringify(data));
      if (plain.type === "init-stage") { stages.push(plain.stage); return; }
      replies.push(plain);
      const resolve = pending.get(plain.reqId);
      if (resolve) { pending.delete(plain.reqId); resolve(plain); }
    },
    ...overrides,
  };
  const context = vm.createContext({ self: worker, URL });
  vm.runInContext(workerSource, context, { filename: "lab-worker.js" });
  return {
    worker, replies, stages, imports, fetches,
    send(request) {
      return new Promise((resolve) => {
        pending.set(request.reqId, resolve);
        worker.onmessage({ data: request });
      });
    },
    emit(type, input = {}) {
      const event = { prevented: false, preventDefault() { this.prevented = true; }, ...input };
      listeners.get(type)(event);
      return event;
    },
  };
}

function init(reqId = "init") {
  return { type: "init", reqId, indexURL, runnerURL };
}

function request(reqId = "run", overrides = {}) {
  return { type: "run", reqId, mode: "run", code: "print(1)", prelude: "", tests: [], seed: null, ...overrides };
}

function stubRuntime() {
  const calls = [];
  const destroyed = [];
  const expected = { ok: true, stdout: "1\n", stderr: "", truncated: false,
    durationMs: 1.5, error: null, checks: [] };
  const runner = (...args) => {
    calls.push(args);
    return {
      toJs(options) {
        assert.equal(JSON.stringify(options.dict_converter([["value", 1]])), '{"value":1}');
        assert.equal(options.create_pyproxies, false);
        return { ...expected };
      },
      destroy() { destroyed.push("result"); },
    };
  };
  runner.destroy = () => destroyed.push("runner");
  return {
    calls, destroyed, expected,
    globals: { get(name) { assert.equal(name, "run_request"); return runner; } },
    runPython(code) {
      calls.push(code);
      return code === runnerSource ? undefined : "3.12.7";
    },
    toPy(data) { return { data, destroy() { destroyed.push("tests"); } }; },
  };
}

test("worker initializes the classic runtime, fetches the runner, and replies with the same reqId", { timeout: 2000 }, async () => {
  const runtime = stubRuntime();
  const state = harness({ async loadPyodide(options) {
    assert.equal(options.indexURL, indexURL);
    return runtime;
  } });
  const result = await state.send(init("i-1"));
  assert.deepEqual(result, { type: "init-ok", reqId: "i-1", pythonVersion: "3.12.7" });
  assert.deepEqual(state.imports, [new URL("pyodide.js", indexURL).href]);
  assert.deepEqual(state.fetches, [runnerURL]);
  assert.equal(runtime.calls[0], runnerSource);
});

for (const stage of ["import", "load", "fetch", "status", "text", "runner", "version"]) {
  test(`worker init failure at ${stage} produces init-error and permits retry`, { timeout: 2000 }, async () => {
    const runtime = stubRuntime();
    let failing = true;
    const state = harness({
      importScripts() { if (failing && stage === "import") { throw new Error("导入失败"); } },
      async loadPyodide() {
        if (failing && stage === "load") { throw new Error("加载失败"); }
        if (failing && (stage === "runner" || stage === "version")) {
          return { runPython(code) {
            if ((code === runnerSource) === (stage === "runner")) { throw new Error("Python 失败"); }
          } };
        }
        return runtime;
      },
      async fetch() {
        if (failing && stage === "fetch") { throw new Error("读取失败"); }
        return { ok: !(failing && stage === "status"), async text() {
          if (failing && stage === "text") { throw new Error("文本失败"); }
          return runnerSource;
        } };
      },
    });
    const result = await state.send(init());
    assert.equal(result.type, "init-error");
    assert.equal(result.reqId, "init");
    assert.ok(result.message.length > 0);
    assert.equal((await state.send(request("not-initialized"))).error.type, "InternalError");
    failing = false;
    assert.equal((await state.send(init("retry"))).type, "init-ok");
  });
}

test("worker queues run behind init and converts results to plain structured data", { timeout: 2000 }, async () => {
  const runtime = stubRuntime();
  let release;
  const state = harness({ loadPyodide() { return new Promise((resolve) => { release = () => resolve(runtime); }); } });
  const initializing = state.send(init());
  const running = state.send(request("r1", { mode: "check", tests: [{ id: "x", name: "检查", code: "assert True" }], seed: 5 }));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(state.replies.length, 0);
  release();
  assert.equal((await initializing).type, "init-ok");
  assert.deepEqual(await running, { ...runtime.expected, type: "run-result", reqId: "r1" });
  const args = runtime.calls[2];
  assert.equal(args[0], "check");
  assert.equal(args[1], "print(1)");
  assert.equal(args[2], "");
  assert.deepEqual(args[3].data, [{ id: "x", name: "检查", code: "assert True" }]);
  assert.equal(args[4], 5);
  assert.deepEqual(runtime.destroyed, ["result", "tests", "runner"]);
});

for (const stage of ["get", "toPy", "call", "convert"]) {
  test(`worker converts ${stage} exceptions to InternalError and recovers`, { timeout: 2000 }, async () => {
    const runtime = stubRuntime();
    const savedGet = runtime.globals.get;
    const savedToPy = runtime.toPy;
    const badRunner = () => {
      if (stage === "call") { throw new Error("调用失败"); }
      return { toJs() { throw new Error("转换失败"); }, destroy() { runtime.destroyed.push("result"); } };
    };
    badRunner.destroy = () => runtime.destroyed.push("runner");
    runtime.globals.get = () => {
      if (stage === "get") { throw new Error("取函数失败"); }
      return badRunner;
    };
    runtime.toPy = (data) => {
      if (stage === "toPy") { throw new Error("取参数失败"); }
      return savedToPy(data);
    };
    const state = harness({ async loadPyodide() { return runtime; } });
    await state.send(init());
    const result = await state.send(request("bad"));
    assert.equal(result.type, "run-result");
    assert.equal(result.reqId, "bad");
    assert.equal(result.ok, false);
    assert.equal(result.error.type, "InternalError");
    assert.equal(result.error.lineno, null);
    assert.deepEqual(result.checks, []);
    assert.deepEqual(runtime.destroyed,
      stage === "get" ? [] : stage === "toPy" ? ["runner"] :
        stage === "call" ? ["tests", "runner"] : ["result", "tests", "runner"]);
    runtime.globals.get = savedGet;
    runtime.toPy = savedToPy;
    assert.equal((await state.send(request("good"))).ok, true);
  });
}

test("worker reports unknown messages instead of becoming silent", { timeout: 2000 }, async () => {
  const state = harness();
  const result = await state.send({ type: "unknown", reqId: "unknown" });
  assert.equal(result.error.type, "InternalError");
  assert.equal(result.reqId, "unknown");
});

test("worker reports uncaught errors and rejections with the most recent request id", { timeout: 2000 }, async () => {
  const state = harness();
  await state.send(request("last-run"));
  for (const [type, input] of [
    ["error", { error: new Error("脚本异常") }],
    ["error", { message: "没有异常对象" }],
    ["unhandledrejection", { reason: new Error("异步异常") }],
  ]) {
    assert.equal(state.emit(type, input).prevented, true);
    const result = state.replies[state.replies.length - 1];
    assert.equal(result.type, "run-result");
    assert.equal(result.reqId, "last-run");
    assert.equal(result.error.type, "InternalError");
    assert.ok(result.error.message.length > 0);
  }
});

const integrationDir = process.env.EBOOK_PYODIDE_DIR || path.join(root, ".pyodide-integration");
const verifiedPath = path.join(integrationDir, "VERIFIED.json");

test("real Pyodide matches CPython through the worker protocol", {
  timeout: 60000,
  skip: !existsSync(verifiedPath) && "先运行 tests/labs/fetch_pyodide.py 获取校验后的测试依赖",
}, async (t) => {
  const verified = JSON.parse(readFileSync(verifiedPath, "utf8"));
  const archive = readFileSync(path.join(integrationDir, "pyodide.tgz"));
  assert.equal(verified.package, "pyodide");
  assert.equal(verified.version, "0.27.7");
  assert.equal("sha512-" + createHash("sha512").update(archive).digest("base64"), verified.integrity);
  const packageDir = path.join(integrationDir, "package");
  const { loadPyodide } = require(path.join(packageDir, "pyodide.js"));
  const savedFetch = globalThis.fetch;
  let python;
  globalThis.fetch = () => { throw new Error("测试禁止任何网络请求"); };
  try {
    python = await loadPyodide({ indexURL: packageDir + path.sep });
  } finally {
    globalThis.fetch = savedFetch;
  }
  const state = harness({ async loadPyodide() { return python; } });
  const initialized = await state.send(init("real-init"));
  assert.equal(initialized.type, "init-ok", initialized.message);
  assert.match(initialized.pythonVersion, /^3\.12\./);
  t.diagnostic(`Pyodide ${verified.version} / Python ${initialized.pythonVersion}`);
  const cases = [
    ["全角标点", request("punctuation", { code: "print（1）" })],
    ["输出行数限制", request("lines", { code: "import sys\nprint('行\\n' * 250, end='')\nsys.stderr.write('错\\n' * 250)" })],
    ["输出字符限制", request("characters", { code: "print('猫' * 20000)" })],
    ["input 提示", request("input", { code: "input('名字？')" })],
    ["准备代码异常", request("prelude", { code: "print('不可执行')", prelude: "1/0" })],
    ["检查执行器与随机重跑", request("checks", {
      mode: "check", seed: 2, prelude: "values = []\nprint('忽略')",
      code: "import random\nvalues.append(random.random())\nprint(values)",
      tests: [
        { id: "pass", name: "重跑", code: "assert RUN_WITH_SEED(2) == STDOUT\nassert RUN_WITH_SEED(1) != STDOUT\nassert len(NS['values']) == 1" },
        { id: "fail", name: "断言消息", code: "assert False, '请再试一次'" },
        { id: "error", name: "检查错误", code: "int('错')" },
      ],
    })],
    ["运行时栈过滤", request("traceback", { code: "import json\ndef f():\n return json.loads('bad')\nf()" })],
    ["命名空间与随机状态隔离", request("isolation", {
      mode: "check", code: "assert 'values' not in globals()\nimport random\nrandom.seed(99)",
      tests: [{ id: "seed", name: "状态隔离", code: "import random\ns = random.getstate()\nRUN_WITH_SEED(1)\nassert random.getstate() == s" }],
    })],
  ];
  const baselineScript = [
    "import importlib.util, json, sys",
    "spec = importlib.util.spec_from_file_location('runner', sys.argv[1])",
    "runner = importlib.util.module_from_spec(spec)",
    "spec.loader.exec_module(runner)",
    "requests = json.load(sys.stdin)",
    "results = [runner.run_request(r['mode'], r['code'], r['prelude'], r['tests'], r['seed']) for r in requests]",
    "print(json.dumps(results, ensure_ascii=False))",
  ].join("\n");
  const baseline = JSON.parse(execFileSync("/home/MyProject/OpenMontage/.venv/bin/python",
    ["-c", baselineScript, runnerPath], {
      input: JSON.stringify(cases.map((entry) => entry[1])), encoding: "utf8",
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
    }));
  for (let index = 0; index < cases.length; index += 1) {
    const [name, input] = cases[index];
    await t.test(name, async () => {
      const result = await state.send(input);
      assert.equal(result.type, "run-result");
      assert.equal(result.reqId, input.reqId);
      assert.ok(result.durationMs >= 0);
      const { type, reqId, durationMs, ...actual } = result;
      const { durationMs: ignoredDuration, ...expected } = baseline[index];
      assert.deepEqual(actual, expected);
    });
  }
});

test("worker reports the steps of the start-up in order, so a hang can be located", { timeout: 2000 }, async () => {
  const h = harness({ async loadPyodide() { return stubRuntime(); } });
  await h.send(init("steps"));
  assert.deepEqual(h.stages.filter((s) => !s.startsWith("fetch ")), ["importScripts", "loadPyodide", "runner"]);
});
