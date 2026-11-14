(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.LabCore = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function asString(value) {
    return typeof value === 'string' ? value : (value == null ? '' : String(value));
  }

  function hashString(value) {
    var text = asString(value);
    var hash = 0x811c9dc5;
    for (var i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return ('00000000' + hash.toString(16)).slice(-8);
  }

  function draftKey(id) {
    return 'ebook.lab.v1.' + asString(id);
  }

  function readDraft(raw, starterHash) {
    if (typeof raw !== 'string' || typeof starterHash !== 'string') return null;
    try {
      var value = JSON.parse(raw);
      if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
      if (value.starterHash !== starterHash || typeof value.code !== 'string' || typeof value.passed !== 'boolean') return null;
      return { code: value.code, passed: value.passed };
    } catch (e) {
      return null;
    }
  }

  function serializeDraft(value) {
    var item = value && typeof value === 'object' ? value : {};
    return JSON.stringify({
      starterHash: typeof item.starterHash === 'string' ? item.starterHash : '',
      code: typeof item.code === 'string' ? item.code : '',
      passed: item.passed === true,
      updatedAt: Object.prototype.hasOwnProperty.call(item, 'updatedAt') ? item.updatedAt : 0
    });
  }

  function normalizeConfig(value) {
    try {
      return { block_paste: !!(value && typeof value === 'object' && !Array.isArray(value) && value.block_paste === true) };
    } catch (e) {
      return { block_paste: false };
    }
  }

  function classifyEnv(value) {
    var env = value && typeof value === 'object' ? value : {};
    if (env.protocol === 'file:') return 'offline';
    if (typeof env.innerWidth === 'number' && env.innerWidth < 600) return 'narrow';
    if (env.hasWorker !== true || env.hasWasm !== true) return 'unsupported';
    return 'ok';
  }

  function normalizeChecks(checks) {
    if (!Array.isArray(checks)) return [];
    return checks.map(function (item) {
      var value = item && typeof item === 'object' ? item : {};
      return {
        id: asString(value.id),
        name: asString(value.name),
        passed: value.passed === true,
        message: asString(value.message)
      };
    });
  }

  function allChecksPassed(checks) {
    return Array.isArray(checks) && checks.length > 0 && checks.every(function (item) { return item && item.passed === true; });
  }

  function solutionUnlocked(failedRuns, shownHints, hintCount) {
    var failures = typeof failedRuns === 'number' && isFinite(failedRuns) ? failedRuns : 0;
    var shown = typeof shownHints === 'number' && isFinite(shownHints) ? shownHints : 0;
    var total = typeof hintCount === 'number' && isFinite(hintCount) ? hintCount : 0;
    return failures >= 2 || (total > 0 && shown >= total);
  }

  function timeoutMessage(seconds) {
    var value = typeof seconds === 'number' && isFinite(seconds) ? seconds : 10;
    return '已超时（' + String(value) + ' 秒），代码已停止';
  }

  function truncateForDisplay(value, limit) {
    var text = asString(value);
    var max = typeof limit === 'number' && isFinite(limit) && limit >= 0 ? Math.floor(limit) : 16384;
    return text.length <= max ? text : text.slice(0, max);
  }

  return {
    hashString: hashString,
    draftKey: draftKey,
    readDraft: readDraft,
    serializeDraft: serializeDraft,
    normalizeConfig: normalizeConfig,
    classifyEnv: classifyEnv,
    normalizeChecks: normalizeChecks,
    allChecksPassed: allChecksPassed,
    solutionUnlocked: solutionUnlocked,
    timeoutMessage: timeoutMessage,
    truncateForDisplay: truncateForDisplay
  };
}));
