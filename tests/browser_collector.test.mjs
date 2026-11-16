import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { makeCollector } from '../scripts/browser_collector.mjs';

const repo = process.cwd();
const python = process.env.CHESSLAB_TEST_PYTHON || 'python3';
async function setup(failClick = false, options = {}) {
  const dir = await mkdtemp(join(tmpdir(), 'chesslab-'));
  const db = join(dir, 'test.sqlite');
  const cfg = join(dir, 'config.json');
  await writeFile(cfg, JSON.stringify({ condition: 'unaided', capabilities: ['screenshot','coordinate_click'],
    model: 'synthetic-fixture', reasoning: 'none', seed: 1, purpose: 'synthetic', permission: 'local fixture' }));
  execFileSync(python, ['-m','chesslab','--db',db,'create','test',cfg], { cwd: repo });
  const calls = [];
  const target = { getScreenshot: async () => Buffer.from('synthetic image bytes'),
    click: async point => { calls.push(point); if (failClick) throw new Error('simulated input failure'); },
    getAXState: async opts => { assert.equal(opts.emit, false); return 'discard this content'; } };
  return { dir, db, calls, target, collector: makeCollector({target,repo,db,run:'test',python,directory:dir,...options}) };
}

test('requires visual verification; persists across recreated helper', async () => {
  const s = await setup();
  try {
    await s.collector.observe({emit:false});
    await s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    assert.equal(s.collector.pending(), '1');
    assert.throws(() => makeCollector({target:s.target,repo,db:s.db,run:'test',python,directory:s.dir}), /EEXIST/);
    s.collector.close();
    const restarted = makeCollector({target:s.target,repo,db:s.db,run:'test',python,directory:s.dir});
    assert.equal(restarted.pending(), '1');
    s.collector = restarted;
    await assert.rejects(restarted.move({actionId:'restart',move:'d2d4',from:[1,2],to:[3,4]}), /pending/);
    await assert.rejects(s.collector.move({actionId:'2',move:'d2d4',from:[1,2],to:[3,4]}), /pending/);
    await s.collector.observe({emit:false});
    s.collector.verify({actionId:'1',outcome:'uncertain',note:'animation'});
    assert.throws(() => s.collector.verify({actionId:'1',outcome:'executed'}), /Observe/);
    assert.equal(s.collector.pending(), '1');
    await s.collector.observe({emit:false});
    s.collector.verify({actionId:'1',outcome:'executed',note:'destination observed'});
    assert.equal(s.collector.pending(), null);
    const r = JSON.parse(execFileSync(python,['-m','chesslab','--db',s.db,'export','test'],{encoding:'utf8'}));
    for (const event of r.events.filter(e => e.payload.screenshot_path)) {
      assert.match(event.payload.screenshot_sha256, /^[0-9a-f]{64}$/);
    }
    assert.equal(s.calls.length, 2);
    await s.collector.observe({emit:false});
    s.collector.terminal({result:'aborted',note:'synthetic smoke complete'});
    await assert.rejects(s.collector.observe({emit:false}));
  } finally { await rm(s.dir,{recursive:true,force:true}); }
});

test('a failed click preserves the pending reservation and does not repeat', async () => {
  const s = await setup(true);
  try {
    await s.collector.observe({emit:false});
    await assert.rejects(s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]}), /simulated/);
    assert.equal(s.collector.pending(), '1');
    assert.throws(() => s.collector.verify({actionId:'1',outcome:'executed'}), /Observe/);
    await assert.rejects(s.collector.move({actionId:'2',move:'e2e4',from:[1,2],to:[3,4]}), /pending/);
    assert.equal(s.calls.length, 1);
  } finally { await rm(s.dir,{recursive:true,force:true}); }
});


test('recovery cannot interleave while a click is in flight', async () => {
  const s = await setup();
  let release;
  try {
    const originalClick = s.target.click;
    s.target.click = async point => {
      await new Promise(resolve => { release = resolve; });
      s.target.click = originalClick;
      await originalClick(point);
    };
    await s.collector.observe({emit:false});
    const moving = s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    while (!release) await new Promise(resolve => setImmediate(resolve));
    assert.throws(() => s.collector.verify({actionId:'1',outcome:'not_executed'}), /in flight/);
    assert.throws(() => s.collector.terminal({result:'aborted'}), /in flight/);
    assert.throws(() => s.collector.close(), /in flight/);
    assert.throws(() => makeCollector({target:s.target,repo,db:s.db,run:'test',python,directory:s.dir}), /EEXIST/);
    await assert.rejects(s.collector.observe({emit:false}), /in flight/);
    await assert.rejects(s.collector.move({actionId:'2',move:'d2d4',from:[5,6],to:[7,8]}), /in flight/);
    release();
    await moving;
    assert.deepEqual(s.calls, [[1,2],[3,4]]);
    assert.equal(s.collector.pending(), '1');
  } finally { if (release) release(); await rm(s.dir,{recursive:true,force:true}); }
});


test('expired deadline and attempt cap block new native input', async () => {
  const expired = await setup(false, { deadline: '2000-01-01T00:00:00Z' });
  try {
    await expired.collector.observe({emit:false});
    await assert.rejects(expired.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]}), /deadline/);
    assert.equal(expired.calls.length, 0);
    assert.equal(expired.collector.pending(), null);
  } finally { await rm(expired.dir,{recursive:true,force:true}); }
  const capped = await setup(false, { maxAttempts: 1 });
  try {
    await capped.collector.observe({emit:false});
    await capped.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    capped.collector.verify({actionId:'1',outcome:'not_executed',note:'synthetic failed choice'});
    await capped.collector.observe({emit:false});
    await assert.rejects(capped.collector.move({actionId:'2',move:'e2e4',from:[1,2],to:[3,4]}), /cap/);
    assert.equal(capped.calls.length, 2);
  } finally { await rm(capped.dir,{recursive:true,force:true}); }
});


test('recreated owner recovers frozen limits and refuses changes', async () => {
  const originalNow = Date.now;
  const deadline = '2030-01-01T00:00:00Z';
  const s = await setup(false, { deadline, maxAttempts: 1 });
  try {
    Date.now = () => Date.parse(deadline) - 1000;
    await s.collector.observe({emit:false});
    await s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    s.collector.verify({actionId:'1',outcome:'not_executed'});
    s.collector.close();
    const base = {target:s.target,repo,db:s.db,run:'test',python,directory:s.dir};
    assert.throws(() => makeCollector({...base,maxAttempts:2}), /mismatch/);
    assert.throws(() => makeCollector({...base,deadline:null}), /mismatch/);
    const restarted = makeCollector(base);
    await restarted.observe({emit:false});
    await assert.rejects(restarted.move({actionId:'2',move:'e2e4',from:[1,2],to:[3,4]}), /cap/);
    Date.now = () => Date.parse(deadline) + 1;
    await assert.rejects(restarted.move({actionId:'2',move:'e2e4',from:[1,2],to:[3,4]}), /deadline/);
    assert.equal(s.calls.length, 2);
  } finally { Date.now = originalNow; await rm(s.dir,{recursive:true,force:true}); }
});

test('deadline crossing during recapture prevents reservation and clicks', async () => {
  const originalNow = Date.now;
  const s = await setup(false, {deadline:'2030-01-01T00:00:00Z'});
  let now = Date.parse('2030-01-01T00:00:00Z') - 1;
  try {
    Date.now = () => now;
    await s.collector.observe({emit:false});
    const originalShot = s.target.getScreenshot;
    s.target.getScreenshot = async (...args) => { now += 2; return originalShot(...args); };
    await assert.rejects(s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]}), /deadline/);
    assert.equal(s.calls.length, 0);
    assert.equal(s.collector.pending(), null);
  } finally { Date.now = originalNow; await rm(s.dir,{recursive:true,force:true}); }
});

test('deadline crossing after reservation retains evidence without clicking', async () => {
  const originalNow = Date.now;
  const end = Date.parse('2030-01-01T00:00:00Z');
  const s = await setup(false, {deadline:'2030-01-01T00:00:00Z'});
  let checks = 0;
  try {
    await s.collector.observe({emit:false});
    Date.now = () => (++checks >= 3 ? end + 1 : end - 1);
    await assert.rejects(s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]}), /deadline/);
    assert.equal(s.calls.length, 0);
    assert.equal(s.collector.pending(), '1');
    const record = JSON.parse(execFileSync(python,['-m','chesslab','--db',s.db,'export','test'],{encoding:'utf8'}));
    assert.ok(record.events.some(event => event.kind === 'observation'
      && event.payload.stage === 'execution' && event.payload.error.includes('deadline')));
  } finally { Date.now = originalNow; await rm(s.dir,{recursive:true,force:true}); }
});


test('promotion is one logged continuation of the existing intent', async () => {
  const s = await setup();
  try {
    await s.collector.observe({emit:false});
    await s.collector.move({actionId:'1',move:'d7d8q',from:[1,2],to:[3,4]});
    s.collector.verify({actionId:'1',outcome:'uncertain',note:'promotion chooser visible'});
    await s.collector.observe({emit:false});
    await assert.rejects(s.collector.promote({actionId:'wrong',at:[5,6]}), /matching/);
    await s.collector.promote({actionId:'1',at:[5,6]});
    assert.equal(s.collector.pending(), '1');
    await assert.rejects(s.collector.promote({actionId:'1',at:[5,6]}), /already reserved/);
    s.collector.verify({actionId:'1',outcome:'executed',note:'promoted piece observed'});
    const r = JSON.parse(execFileSync(python,['-m','chesslab','--db',s.db,'export','test'],{encoding:'utf8'}));
    assert.equal(r.events.filter(e => e.kind === 'intent').length, 1);
    assert.deepEqual(s.calls, [[1,2],[3,4],[5,6]]);
    assert.equal(r.events.filter(e => e.payload.record_type === 'promotion_click_reservation').length, 1);
  } finally { await rm(s.dir,{recursive:true,force:true}); }
});

test('unresolved promotion can halt without pretending the chess move resolved', async () => {
  const s = await setup();
  try {
    await s.collector.observe({emit:false});
    await s.collector.move({actionId:'1',move:'d7d8q',from:[1,2],to:[3,4]});
    s.collector.halt({reason:'collection failure',note:'chooser cannot be resolved'});
    const r = JSON.parse(execFileSync(python,['-m','chesslab','--db',s.db,'export','test'],{encoding:'utf8'}));
    assert.equal(r.events.filter(e => e.kind === 'terminal').length, 0);
    const stopped = r.events.find(e => e.payload.record_type === 'harness_stop');
    assert.equal(stopped.payload.pending_action_id, '1');
    const restarted = makeCollector({target:s.target,repo,db:s.db,run:'test',python,directory:s.dir});
    assert.equal(restarted.pending(), '1');
    await restarted.observe({emit:false});
    await assert.rejects(restarted.promote({actionId:'1',at:[5,6]}), /stopped/);
    await assert.rejects(restarted.move({actionId:'2',move:'d7d8q',from:[1,2],to:[3,4]}), /stopped/);
    assert.throws(() => restarted.verify({actionId:'1',outcome:'executed'}), /stopped/);
    assert.throws(() => restarted.terminal({result:'win'}), /stopped/);
    assert.throws(() => restarted.halt({reason:'again'}), /stopped/);
  } finally { await rm(s.dir,{recursive:true,force:true}); }
});

function exportFixture(s) {
  return JSON.parse(execFileSync(python, ['-m','chesslab','--db',s.db,'export','test'], {cwd:repo,encoding:'utf8'}));
}

test('finish binds verification and terminal to one fresh frame without native calls', async () => {
  for (const outcome of ['executed', 'not_executed']) {
    const s = await setup();
    try {
      await s.collector.observe({emit:false});
      const moved = await s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
      const before = exportFixture(s);
      s.target.getScreenshot = async () => { throw new Error('unexpected capture'); };
      s.target.click = async () => { throw new Error('unexpected click'); };
      s.target.getAXState = async () => { throw new Error('unexpected refresh'); };
      s.collector.finish({actionId:'1',outcome,result:'aborted',note:'synthetic terminal frame'});
      const record = exportFixture(s);
      const [verification, terminal] = record.events.slice(-2);
      assert.equal(verification.kind, 'verification');
      assert.equal(terminal.kind, 'terminal');
      assert.equal(verification.payload.outcome, outcome);
      const source = before.events.at(-1).payload;
      assert.equal(source.file, moved.observation.file);
      for (const event of [verification, terminal]) {
        assert.equal(event.payload.screenshot_path, source.screenshot_path);
        assert.equal(event.payload.screenshot_sha256, source.screenshot_sha256);
        assert.equal(event.payload.observed_at, moved.observation.observed_at);
      }
      assert.equal(record.events.length, before.events.length + 2);
      assert.deepEqual(s.calls, [[1,2],[3,4]]);
      assert.throws(() => s.collector.pending(), /closed/);
      assert.throws(() => s.collector.finish({actionId:'1',outcome,result:'aborted'}), /closed/);
      assert.throws(() => makeCollector({target:s.target,repo,db:s.db,run:'test',python,directory:s.dir}), /already terminal/);
      // A new owner reaching the terminal-ledger guard also proves the old lock closed.
    } finally { await rm(s.dir,{recursive:true,force:true}); }
  }
});

test('finish validates outcome, result and matching action before consuming a frame', async () => {
  const s = await setup();
  try {
    await s.collector.observe({emit:false});
    await s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    const count = exportFixture(s).events.length;
    assert.throws(() => s.collector.finish({actionId:'1',outcome:'uncertain',result:'win'}), /conclusive/);
    assert.throws(() => s.collector.finish({actionId:'1',outcome:'executed',result:'unknown'}), /terminal result/);
    assert.throws(() => s.collector.finish({actionId:'wrong',outcome:'executed',result:'win'}), /pending action/);
    assert.equal(exportFixture(s).events.length, count);
    assert.equal(s.collector.pending(), '1');
    s.collector.finish({actionId:'1',outcome:'executed',result:'win'});
  } finally { await rm(s.dir,{recursive:true,force:true}); }
});

test('finish preserves fresh-observation and halted-run guards', async () => {
  const s = await setup();
  try {
    const ending = {actionId:'1',outcome:'executed',result:'draw'};
    assert.throws(() => s.collector.finish(ending), /Observe/);
    await s.collector.observe({emit:false});
    await s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    s.collector.verify({actionId:'1',outcome:'uncertain'});
    assert.throws(() => s.collector.finish(ending), /Observe/);
    await s.collector.observe({emit:false});
    s.collector.halt({reason:'synthetic stop'});
    assert.throws(() => s.collector.finish(ending), /closed/);
    const restarted = makeCollector({target:s.target,repo,db:s.db,run:'test',python,directory:s.dir});
    await restarted.observe({emit:false});
    assert.throws(() => restarted.finish(ending), /stopped/);
    assert.equal(restarted.pending(), '1');
    assert.equal(exportFixture(s).events.filter(e => e.kind === 'terminal').length, 0);
    restarted.close();
  } finally { await rm(s.dir,{recursive:true,force:true}); }
});

test('finish cannot interleave with a native sequence', async () => {
  const s = await setup();
  let release;
  try {
    const originalClick = s.target.click;
    s.target.click = async point => {
      await new Promise(resolve => { release = resolve; });
      s.target.click = originalClick;
      await originalClick(point);
    };
    await s.collector.observe({emit:false});
    const moving = s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    while (!release) await new Promise(resolve => setImmediate(resolve));
    assert.throws(() => s.collector.finish({actionId:'1',outcome:'executed',result:'win'}), /in flight/);
    assert.equal(exportFixture(s).events.filter(e => e.kind === 'verification').length, 0);
    release();
    await moving;
    s.collector.finish({actionId:'1',outcome:'executed',result:'win'});
  } finally { if (release) release(); await rm(s.dir,{recursive:true,force:true}); }
});

test('finish rejects changed source bytes before verification', async () => {
  const s = await setup();
  try {
    await s.collector.observe({emit:false});
    const moved = await s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    await writeFile(moved.observation.file, 'changed synthetic image');
    assert.throws(() => s.collector.finish({actionId:'1',outcome:'executed',result:'win'}), /artifact changed/);
    assert.equal(s.collector.pending(), '1');
    assert.equal(exportFixture(s).events.filter(e => ['verification','terminal'].includes(e.kind)).length, 0);
  } finally { await rm(s.dir,{recursive:true,force:true}); }
});

test('finish exposes a terminal append failure after preserving the verification', async () => {
  const s = await setup();
  try {
    s.collector.close();
    const wrapper = join(s.dir, 'fail-terminal.py');
    const executable = execFileSync(python, ['-c','import sys; print(sys.executable)'], {encoding:'utf8'}).trim();
    await writeFile(wrapper, `#!${executable}\nimport subprocess, sys\nif 'append' in sys.argv and 'terminal' in sys.argv:\n    sys.exit('synthetic terminal append failure')\nsys.exit(subprocess.run([${JSON.stringify(executable)}, *sys.argv[1:]], input=sys.stdin.buffer.read()).returncode)\n`, {mode:0o700});
    s.collector = makeCollector({target:s.target,repo,db:s.db,run:'test',python:wrapper,directory:s.dir});
    await s.collector.observe({emit:false});
    await s.collector.move({actionId:'1',move:'e2e4',from:[1,2],to:[3,4]});
    assert.throws(() => s.collector.finish({actionId:'1',outcome:'executed',result:'win'}), /synthetic terminal append failure/);
    const record = exportFixture(s);
    assert.equal(record.events.at(-1).kind, 'verification');
    assert.equal(record.events.filter(e => e.kind === 'terminal').length, 0);
    assert.equal(s.collector.pending(), null);
    assert.throws(() => s.collector.finish({actionId:'1',outcome:'executed',result:'win'}), /Observe/);
    assert.throws(() => makeCollector({target:s.target,repo,db:s.db,run:'test',python,directory:s.dir}), /EEXIST/);
    s.collector.close();
  } finally { await rm(s.dir,{recursive:true,force:true}); }
});
