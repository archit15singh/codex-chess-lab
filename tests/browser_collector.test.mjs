import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { makeCollector } from '../scripts/browser_collector.mjs';

const repo = process.cwd();
const python = process.env.CHESSLAB_TEST_PYTHON || 'python3';
async function setup(failClick = false) {
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
  return { dir, db, calls, target, collector: makeCollector({target,repo,db,run:'test',python,directory:dir}) };
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
