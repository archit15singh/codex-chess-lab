/** Native CUA mechanics and evidence only. No chess rules, board parsing or advice.
 * Import in cua_repl and pass the already-selected native app binding.
 * The Python child process writes local evidence; all UI actions use the binding.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync, mkdirSync, writeFileSync, unlinkSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { mkdir, writeFile } from 'node:fs/promises';
import { randomUUID, createHash } from 'node:crypto';
import { join, resolve, dirname } from 'node:path';

const sourceSha256 = createHash('sha256').update(readFileSync(fileURLToPath(import.meta.url))).digest('hex');

export function makeCollector({ target, repo, db, run, python = 'python3', directory }) {
  if (!target || !repo || !db || !run || !directory) throw new Error('Missing collector settings');
  const root = resolve(repo);
  const dir = resolve(directory);
  let lastObservation = null;
  let inFlight = false;
  let closed = false;
  const owners = join(dirname(resolve(db)), '.collector-owners');
  mkdirSync(owners, { recursive: true });
  const key = createHash('sha256').update(JSON.stringify([resolve(db), run])).digest('hex');
  const ownerPath = join(owners, key + '.json');
  const ownerToken = randomUUID();
  // A crashed owner stays locked. Recovery requires authoritative termination
  // evidence, not expiry or a guessed timeout; never steal a live owner's lock.
  writeFileSync(ownerPath, JSON.stringify({ token: ownerToken, run,
    created_at: new Date().toISOString(), pid: process.pid }), { flag: 'wx', mode: 0o600 });
  function assertActive() {
    if (closed) throw new Error('Collector owner closed');
    if (JSON.parse(readFileSync(ownerPath, 'utf8')).token !== ownerToken) {
      throw new Error('Collector owner changed; stop execution');
    }
  }
  function close() {
    if (inFlight) throw new Error('Execution in flight; cannot replace its owner');
    assertActive();
    unlinkSync(ownerPath);
    closed = true;
  }

  function command(args, payload) {
    assertActive();
    const result = execFileSync(python, ['-m', 'chesslab', '--db', resolve(db), ...args], {
      cwd: root, input: payload === undefined ? undefined : JSON.stringify(payload),
      encoding: 'utf8', timeout: 15000, maxBuffer: 2 * 1024 * 1024,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return result.trim() ? JSON.parse(result) : null;
  }
  function append(kind, payload, artifact) {
    command(['append', run, kind, '-', ...(artifact ? ['--artifact', artifact] : [])], payload);
  }
  function pending() {
    let action = null;
    for (const event of command(['export', run]).events) {
      if (event.kind === 'intent') action = event.payload.action_id;
      if (event.kind === 'verification' && event.payload.outcome !== 'uncertain') action = null;
    }
    return action;
  }
  async function capture({ emit = true } = {}) {
    assertActive();
    await mkdir(dir, { recursive: true });
    const bytes = await target.getScreenshot({ emit });
    const file = join(dir, `${run}-${randomUUID()}.png`);
    await writeFile(file, bytes, { flag: 'wx' });
    lastObservation = { file, observed_at: new Date().toISOString() };
    append('tool', { capability: 'screenshot' });
    append('observation', lastObservation, file);
    return { ...lastObservation };
  }
  async function observe(options = {}) {
    if (inFlight) throw new Error('Execution in flight; await its result before recovery');
    return capture(options);
  }
  async function move({ actionId, move, from, to }) {
    if (inFlight) throw new Error('Execution in flight');
    if (pending() !== null) throw new Error('Resolve pending action from a new observation first');
    if (!lastObservation) throw new Error('Observe and select a move before calling move');
    for (const point of [from, to]) {
      if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)) {
        throw new Error('Expected two finite native screenshot coordinates');
      }
    }
    inFlight = true;
    try {
      // Keep the decision image. Recapture records possible intervening changes;
      // it does not automatically establish that the position is unchanged.
      const decision = { ...lastObservation };
      const pre = await capture({ emit: false });
      append('intent', { action_id: actionId, move, from, to,
        decision_screenshot_path: decision.file, decision_observed_at: decision.observed_at,
        before_observed_at: pre.observed_at }, pre.file);
      lastObservation = null;
      append('tool', { capability: 'coordinate_click', action_id: actionId, from, to });
      try {
        await target.click(from);
        await target.click(to);
        // Mandatory host refresh is discarded, never used as chess information.
        await target.getAXState({ emit: false });
        return { action_id: actionId, outcome: 'pending_visual_verification', observation: await capture() };
      } catch (error) {
        lastObservation = null;
        append('observation', { action_id: actionId, error: String(error), stage: 'execution' });
        throw error;
      }
    } finally {
      inFlight = false; // A failed action's ledger reservation remains pending.
    }
  }

  function verify({ actionId, outcome, note }) {
    if (inFlight) throw new Error('Execution in flight; await its result before verification');
    if (!lastObservation) throw new Error('Observe before verifying');
    append('verification', { action_id: actionId, outcome, note,
      observed_at: lastObservation.observed_at }, lastObservation.file);
    lastObservation = null; // Each verification consumes its observation.
  }
  function terminal({ result, note }) {
    assertActive();
    if (inFlight) throw new Error('Execution in flight');
    if (!lastObservation) throw new Error('Observe the terminal UI before recording a result');
    append('terminal', { result, note, observed_at: lastObservation.observed_at }, lastObservation.file);
    close();
  }
  function provenance() {
    append('observation', { driver: 'native-cua', mode: 'screenshot-decisions',
      ax_policy: 'post-action mandatory refresh, discarded; no AX piece/state observations',
      collector_module: import.meta.url, collector_sha256: sourceSha256, collector_version: 2 });
  }
  return { observe, move, verify, terminal, provenance, pending, close };
}
