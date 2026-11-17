import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import pngjs from 'pngjs';
import { bindView, boardDigest } from './browser.mjs';
import { runMatch, validateConfig } from './match.mjs';
import { visionAgent } from './models.mjs';

const config = JSON.parse(await readFile(new URL('../../configs/friend-match.example.json', import.meta.url)));
const move = { status: 'move', from: [4, 6], to: [4, 4], promotion: null };
const accepted = { status: 'accepted' };
const terminal = { status: 'terminal', result: 'black' };

function fixture({ white = ['start', 'start', 'moved'], black = ['reply', 'reply', 'end'],
  whiteReplies = [move, terminal], blackReplies = [accepted, move], failBlackClick = false } = {}) {
  const trace = [];
  let sequence = 0;
  const view = (color, digests) => ({
    async observe() {
      trace.push([color, 'observe']);
      assert.ok(digests.length, 'unexpected observation');
      const boardDigest = digests.shift();
      return { image: Buffer.from(boardDigest), boardDigest };
    },
    async click(at) {
      trace.push([color, 'click', at]);
      if (color === 'black' && failBlackClick) throw new Error('connection lost');
    },
  });
  const model = (color, replies) => async (_prompt, images) => {
    trace.push([color, 'model', images.map(String)]);
    assert.ok(replies.length, 'unexpected model call');
    return replies.shift();
  };
  const journal = {
    async image() { return String(++sequence); },
    async event(kind, data) { trace.push([kind, data]); },
  };
  return { trace, config, journal, views: { white: view('white', white), black: view('black', black) },
    models: { white: model('white', whiteReplies), black: model('black', blackReplies) } };
}

test('alternates tabs only after visual acceptance and stops at a verified result', async () => {
  const match = fixture();
  assert.equal(await runMatch(match), 'black');
  const actions = match.trace.filter(entry => ['click', 'model'].includes(entry[1]));
  assert.deepEqual(actions, [
    ['white', 'model', ['start']],
    ['white', 'click', [487, 607]], ['white', 'click', [487, 457]],
    ['black', 'model', ['start', 'moved']],
    ['black', 'model', ['reply']],
    ['black', 'click', [487, 607]], ['black', 'click', [487, 457]],
    ['white', 'model', ['reply', 'end']],
  ]);
  assert.equal(match.trace.at(-1)[0], 'terminal');
});

test('a stale board stops before any click', async () => {
  const match = fixture({ white: ['start', 'changed'] });
  await assert.rejects(runMatch(match), /Board changed/);
  assert.equal(match.trace.some(entry => entry[1] === 'click'), false);
  assert.equal(match.trace.at(-1)[0], 'stopped');
});

test('uncertain verification never hands over input', async () => {
  const match = fixture({ blackReplies: [{ status: 'uncertain' }] });
  await assert.rejects(runMatch(match), /verification did not confirm/);
  assert.equal(match.trace.some(entry => entry[0] === 'black' && entry[1] === 'observe'), false);
});

test('a failed click leaves its intent in the journal and is never retried', async () => {
  const match = fixture({ failBlackClick: true });
  await assert.rejects(runMatch(match), /connection lost/);
  assert.equal(match.trace.filter(entry => entry[0] === 'black' && entry[1] === 'click').length, 1);
  assert.deepEqual(match.trace.slice(-3).map(entry => entry[0]), ['intent', 'black', 'stopped']);
});

test('a visible promotion is a single journaled continuation', async () => {
  const match = fixture({ white: ['start', 'start', 'chooser', 'chooser', 'promoted'],
    whiteReplies: [{ ...move, promotion: 'q' }, { at: [100, 100] }], blackReplies: [terminal] });
  assert.equal(await runMatch(match), 'black');
  assert.deepEqual(match.trace.filter(entry => entry[1] === 'click').at(-1), ['white', 'click', [220, 140]]);
  assert.equal(match.trace.filter(entry => entry[0] === 'promotion_intent').length, 1);
});

test('rejects two endpoints for the same browser and remote endpoints', () => {
  assert.equal(validateConfig(config), config);
  const duplicate = structuredClone(config);
  duplicate.players.black.endpoint = config.players.white.endpoint.replace(':9225', ':9226');
  assert.throws(() => validateConfig(duplicate), /separate Brave/);
  duplicate.players.black.endpoint = duplicate.players.black.endpoint.replace('127.0.0.1', 'example.org');
  assert.throws(() => validateConfig(duplicate), /loopback/);
});

test('board comparison ignores clock pixels outside the crop', () => {
  const { PNG } = pngjs;
  const png = new PNG({ width: 3, height: 3 });
  const settings = { view: { x: 10, y: 20, width: 3, height: 3 },
    board: { x: 11, y: 21, width: 1, height: 1 } };
  const hash = () => boardDigest(PNG.sync.write(png), settings);
  const original = hash();
  png.data[0] = 0xff;
  assert.equal(hash(), original);
  png.data[16] = 0xff;
  assert.notEqual(hash(), original);
});

test('the browser binding refuses clicks after even same-URL main-frame navigation', async () => {
  const frame = new EventEmitter();
  const tab = new EventEmitter();
  tab.url = () => config.players.white.url;
  tab.isClosed = () => false;
  tab.mainFrame = () => frame;
  tab.mouse = { click() { assert.fail('navigation must block clicks'); } };
  let disconnected = false;
  const view = await bindView(config.players.white, async () => ({
    contexts: () => [{ pages: () => [tab] }], async close() { disconnected = true; },
  }));
  tab.emit('framenavigated', frame);
  await assert.rejects(view.click([120, 120]), /navigated/);
  await view.close();
  assert.ok(disconnected);
});

test('provider adapters send vision input and parse only complete API outputs', async () => {
  for (const provider of ['anthropic', 'openai']) {
    const isClaude = provider === 'anthropic';
    const output = isClaude
      ? { stop_reason: 'end_turn', content: [{ type: 'text', text: '{"status":"accepted"}' }] }
      : { status: 'completed', output: [{ content: [{ type: 'output_text', text: '{"status":"accepted"}' }] }] };
    const agent = visionAgent({ provider, model: 'fixture' }, 'test-key', async (url, options) => {
      const body = JSON.parse(options.body);
      assert.equal(url, isClaude ? 'https://api.anthropic.com/v1/messages' : 'https://api.openai.com/v1/responses');
      const input = (isClaude ? body.messages : body.input)[0].content;
      assert.equal(isClaude ? input[0].source.data : input[0].image_url.split(',')[1], 'cG5n');
      return { ok: true, json: async () => output };
    });
    assert.deepEqual(await agent('Return JSON', [Buffer.from('png')]), accepted);
    if (isClaude) output.stop_reason = 'max_tokens';
    else output.status = 'incomplete';
    await assert.rejects(agent('Return JSON', [Buffer.from('png')]), /did not complete/);
  }
});
