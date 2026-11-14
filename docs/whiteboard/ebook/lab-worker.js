(function () {
  "use strict";

  var python = null;
  var queue = Promise.resolve();
  var current = null;
  var lastRequest = null;

  function messageOf(error) {
    try {
      return error && error.message ? String(error.message) : String(error);
    } catch (_) {
      return "无法读取异常消息";
    }
  }

  function failure(request, error) {
    var message = messageOf(error);
    if (request && request.type === "init") {
      self.postMessage({ type: "init-error", reqId: request.reqId, message: message });
      return;
    }
    self.postMessage({
      type: "run-result", reqId: request && request.reqId || "", ok: false,
      stdout: "", stderr: "", truncated: false, durationMs: 0, checks: [],
      error: { type: "InternalError", message: message, lineno: null, colno: null,
        hintZh: "运行环境出错了，请重试；如果仍然失败，请重新打开页面。", traceback: "" }
    });
  }

  // The page shows the last step reached, so a start-up that hangs in some browser can be located (the steps are also kept for the error report).
  function stage(name) {
    try { self.postMessage({ type: "init-stage", reqId: lastRequest && lastRequest.reqId || "", stage: String(name) }); } catch (_) {}
  }

  function shortName(input) {
    try {
      var address = typeof input === "string" ? input : (input && input.url) || "";
      return new URL(address, self.location.href).pathname.split("/").pop() || "?";
    } catch (_) {
      return "?";
    }
  }

  var instrumented = false;
  function instrument() {
    if (instrumented) { return; }
    instrumented = true;
    try {
      self.addEventListener("securitypolicyviolation", function (event) {
        stage("安全策略拦截：" + event.violatedDirective + " " + (event.blockedURI || ""));
      });
    } catch (_) {}
    try {
      var nativeFetch = self.fetch;
      self.fetch = function (input, init) {
        var name = shortName(input);
        stage("fetch " + name);
        return nativeFetch.call(self, input, init).then(function (response) {
          stage("fetch " + name + " " + response.status);
          return response;
        }, function (error) {
          stage("fetch " + name + " 失败");
          throw error;
        });
      };
    } catch (_) {}
    try {
      ["instantiateStreaming", "instantiate"].forEach(function (key) {
        var native = self.WebAssembly && self.WebAssembly[key];
        if (typeof native !== "function") { return; }
        self.WebAssembly[key] = function () {
          stage("wasm " + key + " 开始");
          return native.apply(self.WebAssembly, arguments).then(function (result) {
            stage("wasm " + key + " 完成");
            return result;
          }, function (error) {
            stage("wasm " + key + " 失败：" + messageOf(error));
            throw error;
          });
        };
      });
    } catch (_) {}
  }

  async function initialize(request) {
    python = null;
    instrument();
    stage("importScripts");
    self.importScripts(new URL("pyodide.js", request.indexURL).href);
    stage("loadPyodide");
    var runtime = await self.loadPyodide({ indexURL: request.indexURL });
    stage("runner");
    var response = await self.fetch(request.runnerURL);
    if (!response.ok) { throw new Error("无法读取 Python 运行器"); }
    runtime.runPython(await response.text());
    var version = runtime.runPython("import sys\nsys.version.split()[0]");
    python = runtime;
    self.postMessage({ type: "init-ok", reqId: request.reqId, pythonVersion: String(version) });
  }

  function run(request) {
    if (!python) { throw new Error("Python 还没有初始化，请重试"); }
    var runner = null;
    var tests = null;
    var result = null;
    try {
      runner = python.globals.get("run_request");
      tests = python.toPy(request.tests);
      result = runner(request.mode, request.code, request.prelude, tests, request.seed);
      var data = result.toJs({ dict_converter: Object.fromEntries, create_pyproxies: false });
      // Pyodide 把 None 转成 undefined；协议要求显式的 null。
      if (data.error == null) {
        data.error = null;
      } else {
        if (data.error.lineno == null) { data.error.lineno = null; }
        if (data.error.colno == null) { data.error.colno = null; }
      }
      data.type = "run-result";
      data.reqId = request.reqId;
      self.postMessage(data);
    } finally {
      [result, tests, runner].forEach(function (proxy) {
        if (proxy && typeof proxy.destroy === "function") { proxy.destroy(); }
      });
    }
  }

  self.onmessage = function (event) {
    var request = event.data;
    queue = queue.then(async function () {
      current = request;
      lastRequest = request;
      try {
        if (!request || typeof request.reqId !== "string") {
          throw new Error("运行请求缺少请求编号");
        }
        if (request.type === "init") {
          await initialize(request);
        } else if (request.type === "run") {
          run(request);
        } else {
          throw new Error("未知的运行线程消息类型");
        }
      } catch (error) {
        failure(request, error);
      } finally {
        current = null;
      }
    }).catch(function (error) { failure(request, error); });
  };

  self.addEventListener("error", function (event) {
    event.preventDefault();
    failure(current || lastRequest, event.error || new Error(event.message || "运行线程发生异常"));
  });
  self.addEventListener("unhandledrejection", function (event) {
    event.preventDefault();
    failure(current || lastRequest, event.reason);
  });
}());
