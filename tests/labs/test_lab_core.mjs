import test from 'node:test';
import assert from 'node:assert/strict';
import LabCore from '../../docs/whiteboard/ebook/lab-core.js';

test('hashes and draft keys are stable', () => {
  assert.equal(LabCore.hashString(''), '811c9dc5');
  assert.equal(LabCore.hashString('abc'), '1a47e90b');
  assert.equal(LabCore.draftKey('s2-u01-draw'), 'ebook.lab.v1.s2-u01-draw');
});

test('draft serialization accepts only matching, usable drafts', () => {
  const raw = LabCore.serializeDraft({ starterHash: 'abcd', code: 'print(1)', passed: true, updatedAt: 12 });
  assert.deepEqual(LabCore.readDraft(raw, 'abcd'), { code: 'print(1)', passed: true });
  assert.equal(LabCore.readDraft(raw, 'wrong'), null);
  assert.equal(LabCore.readDraft('{bad', 'abcd'), null);
  assert.equal(LabCore.readDraft(JSON.stringify({ starterHash: 'abcd', code: 3, passed: true }), 'abcd'), null);
});

test('normalizes hostile configuration inputs to a boolean', () => {
  assert.deepEqual(LabCore.normalizeConfig({ block_paste: true, extra: 1 }), { block_paste: true });
  for (const value of [null, 'yes', 3, [], {}, { block_paste: 'yes' }]) {
    assert.deepEqual(LabCore.normalizeConfig(value), { block_paste: false });
  }
});

test('classifies offline, narrow, unsupported and usable environments', () => {
  assert.equal(LabCore.classifyEnv({ protocol: 'file:', innerWidth: 1000, hasWorker: true, hasWasm: true }), 'offline');
  assert.equal(LabCore.classifyEnv({ protocol: 'https:', innerWidth: 599, hasWorker: true, hasWasm: true }), 'narrow');
  assert.equal(LabCore.classifyEnv({ protocol: 'https:', innerWidth: 800, hasWorker: false, hasWasm: true }), 'unsupported');
  assert.equal(LabCore.classifyEnv({ protocol: 'https:', innerWidth: 800, hasWorker: true, hasWasm: true }), 'ok');
});

test('check and solution helpers cover edge cases', () => {
  assert.equal(LabCore.allChecksPassed([{ id: 'a', passed: true }]), true);
  assert.equal(LabCore.allChecksPassed([]), false);
  assert.deepEqual(LabCore.normalizeChecks([{ id: 1, name: 2, passed: 1, message: null }]), [{ id: '1', name: '2', passed: false, message: '' }]);
  assert.equal(LabCore.solutionUnlocked(1, 1, 2), false);
  assert.equal(LabCore.solutionUnlocked(2, 0, 2), true);
  assert.equal(LabCore.solutionUnlocked(0, 2, 2), true);
  assert.equal(LabCore.timeoutMessage(3), '已超时（3 秒），代码已停止');
});
