(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.LabGuard = factory();
  }
}(globalThis, function () {
  "use strict";

  function isPasteKey(event) {
    if (!event || event.isComposing || event.altKey ||
        (event.type && event.type !== "keydown") ||
        (event.getModifierState && event.getModifierState("AltGraph"))) {
      return false;
    }
    var key = typeof event.key === "string" ? event.key.toLowerCase() : "";
    if ((event.ctrlKey || event.metaKey) && (key === "v" || event.code === "KeyV")) {
      return true;
    }
    return Boolean(event.shiftKey && !event.ctrlKey && !event.metaKey &&
      (key === "insert" || event.code === "Insert"));
  }

  function isPasteInputType(inputType) {
    return inputType === "insertFromPaste" || inputType === "insertFromPasteAsQuotation" ||
      inputType === "insertFromDrop" || inputType === "insertFromYank";
  }

  function install(root, opts) {
    if (!opts.isBlocked()) {
      return { dispose: function () {} };
    }
    var protectedRoot = typeof root.closest === "function" ? root.closest("section.lab") || root : root;
    var composing = false;
    var disposed = false;
    var listeners = [];
    var pasteSubscription = null;

    function active(event) {
      return !disposed && !composing && !(event && event.isComposing) && opts.isBlocked();
    }

    function inside(event, selector, boundary) {
      var scope = boundary || root;
      var target = event.target;
      if (target && target.nodeType === 3) {
        target = target.parentElement;
      }
      var found = target && typeof target.closest === "function" ? target.closest(selector) : null;
      return Boolean(found && (!scope.contains || scope.contains(found)));
    }

    function block(event, kind) {
      if (active(event)) {
        event.preventDefault();
        event.stopPropagation();
        opts.onBlocked(kind);
      }
    }

    function listen(type, handler, target) {
      var scope = target || root;
      scope.addEventListener(type, handler, true);
      listeners.push([scope, type, handler]);
    }

    listen("compositionstart", function () { composing = true; });
    listen("compositionend", function () { composing = false; });
    listen("paste", function (event) { block(event, "paste"); });
    listen("drop", function (event) { block(event, "drop"); });
    listen("dragover", function (event) { block(event, "drop"); });
    listen("keydown", function (event) {
      if (isPasteKey(event)) { block(event, "key"); }
    });
    listen("beforeinput", function (event) {
      if (isPasteInputType(event.inputType)) { block(event, "input"); }
    });
    listen("contextmenu", function (event) {
      if (inside(event, ".lab-editor")) { block(event, "contextmenu"); }
    });
    ["copy", "cut", "dragstart"].forEach(function (type) {
      listen(type, function (event) {
        if (inside(event, ".lab-starter, .lab-hints, .lab-solution", protectedRoot)) {
          block(event, type === "dragstart" ? "drop" : "paste");
        }
      }, protectedRoot);
    });
    if (opts.editor) {
      pasteSubscription = opts.editor.onDidPaste(function (event) {
        var model = typeof opts.editor.getModel === "function" ? opts.editor.getModel() : null;
        if (event && event.range && model && typeof model.getValueInRange === "function" && !model.getValueInRange(event.range)) {
          return;                                   // nothing was inserted, so there is nothing of ours to undo (an undo would take back the learner's own typing)
        }
        if (active()) {
          opts.editor.trigger("lab-guard", "undo", null);
          opts.onBlocked("paste");
        }
      });
    }
    return {
      dispose: function () {
        if (disposed) { return; }
        disposed = true;
        listeners.forEach(function (entry) {
          entry[0].removeEventListener(entry[1], entry[2], true);
        });
        if (pasteSubscription) { pasteSubscription.dispose(); }
      }
    };
  }

  return { isPasteKey: isPasteKey, isPasteInputType: isPasteInputType, install: install };
}));
