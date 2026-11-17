import { createHash, randomUUID } from 'node:crypto';
import { appendFile, mkdir, open, readFile, unlink, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runMatch, validateConfig } from './match.mjs';
import { visionAgent } from './models.mjs';

const repo = fileURLToPath(new URL('../../', import.meta.url));
const keys = { anthropic: 'ANTHROPIC_API_KEY', openai: 'OPENAI_API_KEY' };

async function createJournal(config) {
  const root = resolve(repo, 'evidence/private');
  await mkdir(root, { recursive: true, mode: 0o700 });
  const directory = join(root, `friend-match-${randomUUID()}`);
  await mkdir(directory, { mode: 0o700 });
  const event = (kind, payload) => appendFile(join(directory, 'events.jsonl'),
    JSON.stringify({ at: new Date().toISOString(), kind, ...payload }) + '\n',
    { mode: 0o600, flush: true });
  await event('config', config);
  console.log(`Local evidence: ${directory}`);
  return {
    event,
    async image(image) {
      const filename = `${randomUUID()}.png`;
      await writeFile(join(directory, filename), image, { flag: 'wx', mode: 0o600, flush: true });
      return filename;
    },
  };
}

async function assertFrozen() {
  const manifest = JSON.parse(await readFile(join(repo, 'manifest.json'), 'utf8'));
  if (manifest.profile !== 'friend-match') throw new Error('Expected a frozen friend-match runtime');
  for (const name of ['browser.mjs', 'cli.mjs', 'match.mjs', 'models.mjs', 'package.json', 'package-lock.json']) {
    const relative = `scripts/friend-match/${name}`;
    const actual = createHash('sha256').update(await readFile(join(repo, relative))).digest('hex');
    if (manifest.files[relative] !== actual) throw new Error(`Frozen runtime changed: ${relative}`);
  }
}

async function main([mode, path, ...extras]) {
  if (!['--check', '--live-friend-match'].includes(mode) || !path || extras.length) {
    throw new Error('Usage: node scripts/friend-match/cli.mjs --check|--live-friend-match CONFIG.json');
  }
  const config = validateConfig(JSON.parse(await readFile(path, 'utf8')));
  if (mode === '--check') {
    console.log('Friend-match configuration is valid. No browser or provider was contacted.');
    return;
  }

  await assertFrozen().catch(error => {
    if (error.code === 'ENOENT') throw new Error('Live mode requires the frozen runtime. See docs/friend-match.md.');
    throw error;
  });
  const models = Object.fromEntries(Object.entries(config.players)
    .filter(([color]) => color === 'white' || color === 'black')
    .map(([color, player]) => [color, visionAgent(player, process.env[keys[player.provider]])]));
  const { bindView } = await import('./browser.mjs');
  const lockPath = join(homedir(), '.chesslab-friend-match.lock');
  const lock = await open(lockPath, 'wx', 0o600);
  const views = {};
  try {
    await lock.writeFile(`${process.pid}\n`);
    const journal = await createJournal(config);
    for (const color of ['white', 'black']) views[color] = await bindView(config.players[color]);
    console.log(`Verified match result: ${await runMatch({ views, models, config, journal })}`);
  } finally {
    const closed = await Promise.allSettled(Object.values(views).map(view => view.close()));
    await lock.close();
    if (closed.some(result => result.status === 'rejected')) {
      throw new Error('A browser connection could not be closed. The match lock was retained.');
    }
    await unlink(lockPath);
  }
}

main(process.argv.slice(2)).catch(error => {
  console.error(error.code === 'EEXIST'
    ? 'The match lock or evidence path already exists. Inspect local state before restarting.'
    : error.message);
  process.exitCode = 1;
});
