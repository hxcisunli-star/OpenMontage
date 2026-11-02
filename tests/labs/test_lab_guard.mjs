import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import test from "node:test";

const rootDir = existsSync("docs/whiteboard/ebook/lab-guard.js") ? process.cwd() : path.resolve("out");
const require = createRequire(path.join(rootDir, "tests/labs/test_lab_guard.mjs"));
const sourcePath = path.join(rootDir, "docs/whiteboard/ebook/lab-guard.js");
const guard = require(sourcePath);

function keyEvent(overrides = {}) {
  return { type: "keydown", key: "v", code: "KeyV", ctrlKey: false, metaKey: false,
    shiftKey: false, altKey: false, isComposing: false, ...overrides };
}

const pasteKeys = [
  ["Ctrl+V", { ctrlKey: true }],
  ["Ctrl+Shift+V", { ctrlKey: true, shiftKey: true, key: "V" }],
  ["Cmd+V", { metaKey: true }],
  ["Cmd+Shift+V", { metaKey: true, shiftKey: true, key: "V" }],
  ["Shift+Insert by key", { shiftKey: true, key: "Insert", code: "" }],
  ["Shift+Insert by code", { shiftKey: true, key: "Unidentified", code: "Insert" }],
  ["non-Latin physical V", { ctrlKey: true, key: "м", code: "KeyV" }],
  ["logical V on another key", { metaKey: true, key: "v", code: "KeyQ" }],
  ["missing key but physical V", { ctrlKey: true, key: undefined }],
];
pasteKeys.forEach(([name, input]) => {
  test(`paste key: ${name}`, () => assert.equal(guard.isPasteKey(keyEvent(input)), true));
});

const normalKeys = [
  ["plain v", {}],
  ["plain V", { key: "V", shiftKey: true }],
  ["Ctrl+C", { ctrlKey: true, key: "c", code: "KeyC" }],
  ["Ctrl+X", { ctrlKey: true, key: "x", code: "KeyX" }],
  ["Cmd+C", { metaKey: true, key: "c", code: "KeyC" }],
  ["Cmd+X", { metaKey: true, key: "x", code: "KeyX" }],
  ["AltGr", { ctrlKey: true, altKey: true }],
  ["AltGraph state", { ctrlKey: true, getModifierState: (name) => name === "AltGraph" }],
  ["Alt+V", { altKey: true }],
  ["Cmd+Alt+V", { metaKey: true, altKey: true }],
  ["composing Ctrl+V", { ctrlKey: true, isComposing: true }],
  ["composing Shift+Insert", { key: "Insert", code: "Insert", shiftKey: true, isComposing: true }],
  ["plain Insert", { key: "Insert", code: "Insert" }],
  ["Ctrl+Insert copies", { ctrlKey: true, key: "Insert", code: "Insert" }],
  ["keyup", { type: "keyup", ctrlKey: true }],
  ["another control key", { key: "Enter", code: "Enter", ctrlKey: true }],
];
normalKeys.forEach(([name, input]) => {
  test(`normal key: ${name}`, () => assert.equal(guard.isPasteKey(keyEvent(input)), false));
});

test("empty key event is safe", () => {
  assert.equal(guard.isPasteKey(null), false);
  assert.equal(guard.isPasteKey({}), false);
});

["insertFromPaste", "insertFromPasteAsQuotation", "insertFromDrop", "insertFromYank"].forEach((inputType) => {
  test(`paste input: ${inputType}`, () => assert.equal(guard.isPasteInputType(inputType), true));
});
["insertCompositionText", "insertText", "historyUndo", "historyRedo", "deleteContentBackward",
  "insertReplacementText", "", null, undefined].forEach((inputType) => {
  test(`normal input: ${inputType}`, () => assert.equal(guard.isPasteInputType(inputType), false));
});

class Element {
  constructor(className = "", parent = null) {
    this.className = className;
    this.parentElement = parent;
  }
  closest(selector) {
    const classes = selector.split(",").map((part) => part.trim().slice(1));
    for (let element = this; element; element = element.parentElement) {
      if (classes.includes(element.className)) { return element; }
    }
    return null;
  }
  contains(target) {
    for (let element = target; element; element = element.parentElement) {
      if (element === this) { return true; }
    }
    return false;
  }
}

class Root extends Element {
  constructor() {
    super("lab");
    this.listeners = new Map();
    this.additions = [];
    this.removals = [];
  }
  addEventListener(type, callback, capture) {
    assert.equal(this.listeners.has(type), false);
    this.listeners.set(type, callback);
    this.additions.push([type, callback, capture]);
  }
  removeEventListener(type, callback, capture) {
    assert.equal(this.listeners.get(type), callback);
    this.listeners.delete(type);
    this.removals.push([type, callback, capture]);
  }
  fire(type, input = {}) {
    const event = { type, target: this, prevented: false, stopped: false,
      preventDefault() { this.prevented = true; },
      stopPropagation() { this.stopped = true; }, ...input };
    const handler = this.listeners.get(type);
    if (handler) { handler(event); }
    return event;
  }
}

function setup(initiallyBlocked = true) {
  const root = new Root();
  const calls = [];
  let blocked = initiallyBlocked;
  let pasteCallback;
  let editorSubscriptions = 0;
  let editorDisposals = 0;
  const triggers = [];
  const editor = {
    onDidPaste(callback) {
      pasteCallback = callback;
      editorSubscriptions += 1;
      return { dispose() { editorDisposals += 1; } };
    },
    trigger(...args) { triggers.push(args); },
  };
  const handle = guard.install(root, {
    isBlocked: () => blocked, onBlocked: (kind) => calls.push(kind), editor,
  });
  return { root, calls, handle, triggers, setBlocked(value) { blocked = value; },
    paste(event) { pasteCallback(event); }, get editorSubscriptions() { return editorSubscriptions; },
    get editorDisposals() { return editorDisposals; } };
}

test("UMD exposes the browser global without touching DOM", () => {
  const context = vm.createContext({});
  vm.runInContext(readFileSync(sourcePath, "utf8"), context);
  assert.equal(typeof context.LabGuard.install, "function");
  assert.equal(context.LabGuard.isPasteKey(keyEvent({ metaKey: true })), true);
});

test("allowed at installation means zero DOM and editor listeners", () => {
  const state = setup(false);
  assert.equal(state.root.additions.length, 0);
  assert.equal(state.editorSubscriptions, 0);
  state.setBlocked(true);
  assert.equal(state.root.fire("paste").prevented, false);
  state.handle.dispose();
  state.handle.dispose();
  assert.equal(state.root.removals.length, 0);
  assert.equal(state.editorDisposals, 0);
});

[
  ["paste", {}, "paste"],
  ["drop", {}, "drop"],
  ["dragover", {}, "drop"],
  ["keydown", keyEvent({ ctrlKey: true }), "key"],
  ["beforeinput", { inputType: "insertFromPaste" }, "input"],
  ["beforeinput", { inputType: "insertFromPasteAsQuotation" }, "input"],
  ["beforeinput", { inputType: "insertFromDrop" }, "input"],
].forEach(([type, event, kind]) => {
  test(`blocks ${type} ${event.inputType || ""} in capture phase`, () => {
    const state = setup();
    const result = state.root.fire(type, event);
    assert.equal(result.prevented, true);
    assert.equal(result.stopped, true);
    assert.deepEqual(state.calls, [kind]);
    assert.equal(state.root.additions.every((entry) => entry[2] === true), true);
    state.handle.dispose();
  });
});

test("normal typing and undo are allowed", () => {
  const state = setup();
  for (const [, input] of normalKeys) {
    const result = state.root.fire("keydown", keyEvent(input));
    assert.equal(result.prevented, false);
  }
  for (const inputType of ["insertCompositionText", "insertText", "historyUndo", "historyRedo"]) {
    assert.equal(state.root.fire("beforeinput", { inputType }).prevented, false);
  }
  assert.deepEqual(state.calls, []);
});

for (const className of ["lab-starter", "lab-hints", "lab-solution"]) {
  for (const type of ["copy", "cut", "dragstart"]) {
    test(`blocks ${type} from nested ${className}`, () => {
      const state = setup();
      const target = new Element("code", new Element(className, state.root));
      const result = state.root.fire(type, { target });
      assert.equal(result.prevented, true);
      assert.equal(result.stopped, true);
      assert.deepEqual(state.calls, [type === "dragstart" ? "drop" : "paste"]);
    });
  }
}

test("editor and output copy/cut/dragstart stay available", () => {
  const state = setup();
  for (const className of ["lab-editor", "lab-out", "lab-err"]) {
    const target = new Element(className, state.root);
    for (const type of ["copy", "cut", "dragstart"]) {
      const result = state.root.fire(type, { target });
      assert.equal(result.prevented, false);
      assert.equal(result.stopped, false);
    }
  }
  assert.deepEqual(state.calls, []);
});

test("only the editor context menu is blocked", () => {
  const state = setup();
  const editor = new Element("lab-editor", state.root);
  assert.equal(state.root.fire("contextmenu", { target: new Element("textarea", editor) }).prevented, true);
  assert.equal(state.root.fire("contextmenu", { target: new Element("lab-out", state.root) }).prevented, false);
  assert.deepEqual(state.calls, ["contextmenu"]);
});

test("text-node targets work and elements outside root are not matched", () => {
  const state = setup();
  const text = { nodeType: 3, parentElement: new Element("lab-hints", state.root) };
  assert.equal(state.root.fire("copy", { target: text }).prevented, true);
  assert.equal(state.root.fire("copy", { target: new Element("lab-hints") }).prevented, false);
  assert.equal(state.root.fire("copy", { target: null }).prevented, false);
});

test("composition allows every guarded event and the Monaco fallback", () => {
  const state = setup();
  const starter = new Element("lab-starter", state.root);
  state.root.fire("compositionstart");
  for (const [type, input] of [
    ["paste", {}], ["drop", {}], ["dragover", {}], ["keydown", keyEvent({ ctrlKey: true })],
    ["beforeinput", { inputType: "insertFromPaste" }],
    ["contextmenu", { target: new Element("lab-editor", state.root) }],
    ["copy", { target: starter }], ["cut", { target: starter }], ["dragstart", { target: starter }],
  ]) {
    assert.equal(state.root.fire(type, input).prevented, false);
  }
  state.paste();
  assert.deepEqual(state.calls, []);
  assert.deepEqual(state.triggers, []);
  state.root.fire("compositionend");
  assert.equal(state.root.fire("paste").prevented, true);
  assert.equal(state.root.fire("paste", { isComposing: true }).prevented, false);
});

test("isBlocked is consulted again for every event and editor fallback", () => {
  const state = setup();
  state.setBlocked(false);
  assert.equal(state.root.fire("paste").prevented, false);
  state.paste();
  assert.deepEqual(state.calls, []);
  assert.deepEqual(state.triggers, []);
  state.setBlocked(true);
  assert.equal(state.root.fire("paste").prevented, true);
});

test("Monaco fallback undoes the paste once with the required trigger arguments", () => {
  const state = setup();
  state.paste();
  assert.deepEqual(state.triggers, [["lab-guard", "undo", null]]);
  assert.deepEqual(state.calls, ["paste"]);
});

test("dispose removes every listener and the editor subscription exactly once", () => {
  const state = setup();
  assert.equal(state.root.additions.length, 11);
  state.handle.dispose();
  assert.deepEqual(state.root.removals, state.root.additions);
  assert.equal(state.root.listeners.size, 0);
  assert.equal(state.editorDisposals, 1);
  state.handle.dispose();
  assert.equal(state.editorDisposals, 1);
  state.paste();
  assert.equal(state.root.fire("paste").prevented, false);
  assert.deepEqual(state.triggers, []);
  assert.deepEqual(state.calls, []);
});

test("null editor is supported", () => {
  const root = new Root();
  const handle = guard.install(root, { isBlocked: () => true, editor: null, onBlocked() {} });
  assert.equal(root.fire("paste").prevented, true);
  handle.dispose();
  assert.equal(root.listeners.size, 0);
});

test("the editor fallback undoes a real paste but never undoes when nothing was inserted", () => {
  const empty = { getModel() { return { getValueInRange() { return ""; } }; } };
  const filled = { getModel() { return { getValueInRange() { return "abc"; } }; } };
  [[empty, 0], [filled, 1]].forEach(([extra, undoes]) => {
    let pasteCallback = null;
    const triggers = [];
    const root = { addEventListener() {}, removeEventListener() {}, contains: () => true };
    guard.install(root, { isBlocked: () => true, onBlocked() {}, editor: Object.assign({
      onDidPaste(cb) { pasteCallback = cb; return { dispose() {} }; }, trigger(...args) { triggers.push(args); } }, extra) });
    pasteCallback({ range: { startLineNumber: 1 } });
    assert.equal(triggers.length, undoes);
  });
});
