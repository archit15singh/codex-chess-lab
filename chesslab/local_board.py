"""One frozen local chess game. Player HTTP routes expose only the visible board.

Controller records/token remain outside the served routes. This is a procedural
information contract, not a sandbox against a player with arbitrary local tools.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
from urllib.parse import urlsplit

import chess
import chess.engine
import chess.svg


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('nonfinite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def configuration(value):
    required = {'mode', 'start_fen', 'player_color', 'orientation', 'decision_seconds',
                'wall_seconds', 'engine'}
    if set(value) != required or value['mode'] not in {'controlled', 'manual_fixture'}:
        raise ValueError('explicit local-board configuration keys/mode required')
    board = chess.Board(value['start_fen'])
    if not board.is_valid() or board.chess960:
        raise ValueError('valid standard chess start FEN required')
    for field in ['player_color', 'orientation']:
        if value[field] not in {'white', 'black'}:
            raise ValueError('color/orientation must be white or black')
    for field in ['decision_seconds', 'wall_seconds']:
        if type(value[field]) not in (int, float) or not 0 < value[field] <= 86400:
            raise ValueError('finite positive clock limit required')
    result = dict(value)
    if value['mode'] == 'manual_fixture':
        if value['engine'] is not None:
            raise ValueError('manual fixtures must not start an engine')
    else:
        engine = value['engine']
        if not isinstance(engine, dict) or set(engine) != {'path', 'options', 'nodes', 'movetime_ms', 'timeout_seconds'}:
            raise ValueError('explicit engine configuration required')
        path = Path(engine['path']).resolve(strict=True)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError('executable engine required')
        if (engine['nodes'] is None) == (engine['movetime_ms'] is None):
            raise ValueError('choose exactly one node or movetime budget')
        for key in ['nodes', 'movetime_ms']:
            if engine[key] is not None and (type(engine[key]) is not int or engine[key] <= 0):
                raise ValueError('positive integer engine budget required')
        if type(engine['timeout_seconds']) not in (int, float) or not 0 < engine['timeout_seconds'] <= 120:
            raise ValueError('bounded engine timeout required')
        if engine['movetime_ms'] is not None and engine['movetime_ms'] > engine['timeout_seconds'] * 1000:
            raise ValueError('movetime must fit configured engine timeout')
        if not isinstance(engine['options'], dict):
            raise ValueError('engine options object required')
        external = {}
        for key, option in engine['options'].items():
            if not isinstance(key, str) or type(option) not in (str, int, bool):
                raise ValueError('scalar UCI options required')
            if key.lower().startswith('evalfile') and option:
                network = Path(option).resolve(strict=True)
                external[str(network)] = sha(network)
        result['engine'] = {**engine, 'path': str(path), 'binary_sha256': sha(path),
                            'external_network_sha256': external}
    return result


def create_run(directory, config):
    """Freeze config only; no game/subject clock or engine is started here."""
    frozen = configuration(config)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_new(directory / 'config.json', frozen)
    write_new(directory / 'freeze.json', {'config_sha256': sha(directory / 'config.json'),
              'source_sha256': sha(__file__), 'schema_version': 1})
    with (directory / 'controller-token').open('x') as stream:
        stream.write(secrets.token_urlsafe(32))
    os.chmod(directory / 'controller-token', 0o600)
    return directory


class EngineExitUnconfirmed(TimeoutError):
    """Keep ownership when actual subprocess exit has not been observed."""


class EngineOpponent:
    def __init__(self, config):
        try:
            self.worker = chess.engine.SimpleEngine.popen_uci(config['path'], timeout=config['timeout_seconds'])
        except BaseException as exc:
            # Initialization can fail after spawning; no returned process handle means
            # this caller cannot attest cleanup. Preserve the owner for inspection.
            raise EngineExitUnconfirmed('engine initialization exit unobserved') from exc
        try:
            self.worker.configure(config['options'])
        except BaseException:
            self.close()
            raise
        self.config = config
        self.identity = {'engine_id': dict(self.worker.id), 'option_defaults': {name: option.default for name, option in self.worker.options.items()}, 'configured_options': config['options']}

    def move(self, board):
        # No analysis/PV is returned to the player. Budget and actual work remain private.
        limit = chess.engine.Limit(nodes=self.config['nodes'],
                  time=self.config['movetime_ms'] / 1000 if self.config['movetime_ms'] else None)
        result = self.worker.play(board, limit, info=chess.engine.INFO_BASIC)
        self.last_info = {k: result.info.get(k) for k in ['nodes', 'time', 'depth']}
        return result.move

    def close(self):
        try:
            self.worker.close()
            code = self.worker.returncode.result(timeout=2)
            if type(code) is not int:
                raise ValueError('missing engine process returncode')
            return code
        except BaseException as exc:
            raise EngineExitUnconfirmed('actual engine process exit unobserved') from exc


class Game:
    """Serialized intent/action/rules/clock interface with append-only private evidence."""
    def __init__(self, directory, *, clock=time.monotonic, engine_factory=EngineOpponent):
        self.directory = Path(directory).resolve(strict=True)
        freeze = strict_json((self.directory / 'freeze.json').read_bytes())
        if sha(self.directory / 'config.json') != freeze['config_sha256'] or sha(__file__) != freeze['source_sha256']:
            raise ValueError('frozen source/config changed')
        self.config = strict_json((self.directory / 'config.json').read_bytes())
        self.board = chess.Board(self.config['start_fen'])
        self.player = self.config['player_color'] == 'white'
        self.clock = clock
        self.lock = threading.RLock()
        self.version = 0
        self.seen = set()
        self.status = 'running'
        self.result = '*'
        self.reason = None
        self.opponent = None
        self.opponent_closed = False
        self.closed = False
        self.worker = None
        self.sequence = 0
        self.previous_hash = None
        # Exclusive open is also the no-resume/no-retry gate, including partial failures.
        self.journal = (self.directory / 'events.jsonl').open('x')
        try:
            engine = self.config['engine']
            if engine:
                if sha(engine['path']) != engine['binary_sha256'] or any(sha(p) != h for p, h in engine['external_network_sha256'].items()):
                    raise ValueError('engine binary/network changed')
                if not self.board.is_game_over():
                    active_started = time.monotonic_ns()
                    try:
                        self.opponent = engine_factory(engine)
                    finally:
                        self._event('engine_active_segment', phase='startup',
                                    active_ns=time.monotonic_ns() - active_started)
            self.started = self.clock()
            self.turn_started = self.started
            self._event('game_started', mode=self.config['mode'], config_sha256=freeze['config_sha256'],
                        engine_identity=self.opponent.identity if self.opponent else None)
            self._automatic_end()
            self._persist()
            self._start_opponent()
        except BaseException as exc:
            self._event('startup_failure', error_type=type(exc).__name__)
            try:
                if self.opponent:
                    self._close_opponent()
            finally:
                self.journal.close()
            raise

    def _event(self, kind, **details):
        self.sequence += 1
        event = {'sequence': self.sequence, 'at': datetime.now(timezone.utc).isoformat(),
                 'kind': kind, 'version': self.version, 'previous_sha256': self.previous_hash, **details}
        raw = json.dumps(event, sort_keys=True, allow_nan=False)
        self.journal.write(raw + '\n')
        self.journal.flush()
        os.fsync(self.journal.fileno())
        self.previous_hash = hashlib.sha256(raw.encode()).hexdigest()

    def _persist(self):
        path = self.directory / 'state.json.part'
        with path.open('x') as stream:
            json.dump(self._private(), stream, indent=2)
            stream.write('\n')
        os.replace(path, self.directory / 'state.json')

    def _private(self):
        return {'version': self.version, 'fen': self.board.fen(),
                'moves': [m.uci() for m in self.board.move_stack], 'status': self.status,
                'result': self.result, 'reason': self.reason, 'event_sha256': self.previous_hash,
                'config_sha256': sha(self.directory / 'config.json')}

    def _end(self, reason, result='*'):
        if self.status == 'running':
            self.status, self.reason, self.result = 'ended', reason, result
            self.version += 1
            self._event('game_ended', reason=reason, result=result, fen=self.board.fen())
            if self.opponent:
                try:
                    self._close_opponent()
                except Exception as exc:
                    self._event('opponent_cleanup_failure', error_type=type(exc).__name__)

    def _close_opponent(self):
        if self.opponent and not self.opponent_closed:
            active_started = time.monotonic_ns()
            try:
                code = self.opponent.close()  # Returns only after proven process exit.
            finally:
                self._event('engine_active_segment', phase='cleanup',
                            active_ns=time.monotonic_ns() - active_started)
            self.opponent_closed = True
            self._event('opponent_closed', process_returncode=code)

    def _automatic_end(self):
        outcome = self.board.outcome(claim_draw=False)
        if outcome:
            self._end(outcome.termination.name.lower(), outcome.result())

    def _tick(self):
        if self.status != 'running':
            return
        elapsed = self.clock() - self.started
        if elapsed >= self.config['wall_seconds']:
            self._end('wall_timeout')
        elif self.board.turn == self.player and self.clock() - self.turn_started >= self.config['decision_seconds']:
            self._end('decision_timeout')

    def tick(self):
        with self.lock:
            if self.closed:
                return
            before = self.version
            self._tick()
            if before != self.version:
                self._persist()

    def public(self):
        with self.lock:
            self.tick()
            remaining = max(0, self.config['decision_seconds'] - (self.clock() - self.turn_started))
            return {'version': self.version, 'status': self.status, 'result': self.result,
                    'your_turn': self.status == 'running' and self.board.turn == self.player,
                    'message': self.reason.replace('_', ' ') if self.reason else ('Your turn' if self.board.turn == self.player else 'Opponent turn'),
                    'decision_remaining_seconds': remaining if self.board.turn == self.player and self.status == 'running' else None}

    def svg(self):
        with self.lock:
            self.tick()
            return chess.svg.board(self.board, orientation=self.config['orientation'] == 'white',
                                   coordinates=False, size=640, lastmove=None, check=None)

    def private(self):
        with self.lock:
            self.tick()
            return self._private()

    def action(self, data, *, fixture=False):
        with self.lock:
            if self.closed:
                raise ValueError('server closed')
            self.tick()
            if set(data) - {'intent_id', 'version', 'kind', 'from', 'to', 'promotion'} or not {'intent_id', 'version', 'kind'} <= set(data):
                raise ValueError('action fields')
            intent = data['intent_id']
            if not isinstance(intent, str) or not 1 <= len(intent) <= 100 or intent in self.seen:
                raise ValueError('duplicate or invalid intent')
            self.seen.add(intent)
            self._event('intent', intent_id=intent, action=data, fen_before=self.board.fen())
            try:
                if type(data['version']) is not int or data['version'] != self.version:
                    raise ValueError('stale board version')
                if self.status != 'running':
                    raise ValueError('game ended')
                if fixture and self.config['mode'] != 'manual_fixture':
                    raise ValueError('fixture actions disabled')
                if not fixture and self.board.turn != self.player:
                    raise ValueError('not player turn')
                kind = data['kind']
                if kind == 'resign':
                    self._end('resignation', '0-1' if self.player else '1-0')
                elif kind in {'move', 'claim_draw'}:
                    candidate = self.board
                    move = None
                    if 'from' in data or 'to' in data:
                        start, end = chess.parse_square(data['from']), chess.parse_square(data['to'])
                        piece = self.board.piece_at(start)
                        promotion = data.get('promotion', 'q')
                        if promotion not in {'q', 'r', 'b', 'n'}:
                            raise ValueError('promotion choice required')
                        promotes = piece and piece.piece_type == chess.PAWN and chess.square_rank(end) in {0, 7}
                        move = chess.Move(start, end, promotion=chess.Piece.from_symbol(promotion).piece_type if promotes else None)
                        if move not in self.board.legal_moves:
                            raise ValueError('illegal move')
                        candidate = self.board.copy(stack=True)
                        candidate.push(move)
                    if kind == 'claim_draw':
                        if not (candidate.is_repetition(3) or candidate.is_fifty_moves()):
                            raise ValueError('draw not claimable')
                        self._end('claimed_draw', '1/2-1/2')
                    elif move is None:
                        raise ValueError('move squares required')
                    else:
                        self.board.push(move)
                        self.version += 1
                        self.turn_started = self.clock()
                        self._event('move_applied', intent_id=intent, move=move.uci(), fen_after=self.board.fen())
                        self._automatic_end()
                else:
                    raise ValueError('unknown action')
            except (ValueError, KeyError, TypeError) as exc:
                self._event('intent_rejected', intent_id=intent, error_type=type(exc).__name__)
                self._persist()
                raise ValueError(str(exc)) from exc
            self._persist()
            self._start_opponent()
            return self.public()

    def _start_opponent(self):
        if self.status != 'running' or self.board.turn == self.player or not self.opponent:
            return
        version, board = self.version, self.board.copy(stack=True)
        self._event('opponent_started', expected_version=version)
        self._persist()
        self.worker = threading.Thread(target=self._opponent_move, args=(version, board), daemon=True)
        self.worker.start()

    def _opponent_move(self, version, board):
        started = time.monotonic()
        try:
            active_started = time.monotonic_ns()
            try:
                move = self.opponent.move(board)
            finally:
                active_ns = time.monotonic_ns() - active_started
                with self.lock:
                    self._event('engine_active_segment', phase='search', active_ns=active_ns,
                                expected_version=version)
            with self.lock:
                self._event('opponent_returned', elapsed_seconds=time.monotonic() - started,
                            work=getattr(self.opponent, 'last_info', {}))
                self._tick()
                if self.status != 'running' or self.version != version:
                    self._event('opponent_result_ignored', original_version=version)
                elif move is None or move not in self.board.legal_moves:
                    raise ValueError('opponent returned no legal move')
                else:
                    self.board.push(move)
                    self.version += 1
                    self.turn_started = self.clock()
                    self._event('opponent_move_applied', move=move.uci(), fen_after=self.board.fen())
                    self._automatic_end()
                self._persist()
        except Exception as exc:
            with self.lock:
                self._event('opponent_failure', error_type=type(exc).__name__, elapsed_seconds=time.monotonic() - started)
                self._end('opponent_error')
                self._persist()

    def close(self, *, join_timeout=2):
        with self.lock:
            if self.closed:
                return
            if self.status == 'running':
                self._end('operator_stopped')
                self._persist()
            try:
                self._close_opponent()  # Recheck cleanup if _end could not attest it.
            except Exception:
                self._event('shutdown_blocked', engine_process_exit_unconfirmed=True)
                self._persist()
                raise
        if self.worker:
            self.worker.join(timeout=join_timeout)
            if self.worker.is_alive():
                with self.lock:
                    self._event('shutdown_blocked', worker_alive=True, join_timeout_seconds=join_timeout)
                    self._persist()
                raise TimeoutError('opponent worker still alive; preserve journal and owner lease')
        with self.lock:
            self.closed = True
            self.journal.close()


PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Chess table</title>
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#18211f;color:#eee9dc;font:18px Georgia,serif}main{max-width:760px;margin:30px auto;padding:0 30px}header{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #63746b;margin-bottom:20px}h1{font-weight:normal;font-size:30px;letter-spacing:.02em}#status{font:16px monospace;color:#e5cb91}.frame{display:grid;grid-template-columns:22px 1fr;gap:6px}.ranks{display:flex;flex-direction:column;justify-content:space-around;text-align:center;font:14px monospace}.files{grid-column:2;display:flex;justify-content:space-around;font:14px monospace}#board{width:100%;height:auto;display:block;cursor:pointer;touch-action:manipulation}button,select{background:#253a30;color:#fff4d8;border:1px solid #718c78;border-radius:3px;padding:10px;font:15px Georgia,serif}button:focus-visible,select:focus-visible{outline:3px solid #e5cb91}footer{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:20px}#notice{min-height:1.5em;font:15px monospace;color:#e5cb91}label{font-size:14px}@media(max-width:600px){main{padding:0 12px;margin:12px auto}header{display:block}h1{margin-bottom:8px}}</style>
<main><header><h1>Chess table</h1><span id="status" aria-live="polite">Loading board</span></header><div class="frame"><div class="ranks">RANKS</div><img id="board" src="/board.svg" width="640" height="640" alt="Chess board"><div class="files">FILES</div></div><p id="notice" aria-live="polite"></p><footer><label>Promotion <select id="promotion"><option value="q">Queen</option><option value="r">Rook</option><option value="b">Bishop</option><option value="n">Knight</option></select></label><label><input type="checkbox" id="claim-next">Claim with next move</label><button id="draw">Claim draw</button><button id="resign">Resign</button></footer></main>
<script nonce="NONCE">const white=ORIENTATION;let version=-1,active=false,selected=null,busy=false;const img=document.getElementById('board'),notice=document.getElementById('notice');
async function refresh(){const r=await fetch('/view',{cache:'no-store'}),v=await r.json();if(v.version<version)return;if(version!==v.version){version=v.version;img.src='/board.svg?v='+version;selected=null}active=v.your_turn;document.getElementById('status').textContent=v.message+(v.decision_remaining_seconds===null?'':' · '+Math.ceil(v.decision_remaining_seconds)+'s')+(v.status==='ended'?' · '+v.result:'')}
async function send(kind,extra={}){if(busy)return;busy=true;try{const r=await fetch('/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({intent_id:crypto.randomUUID(),version,kind,...extra})});notice.textContent=r.ok?'':(await r.json()).error;await refresh()}catch(e){active=false;notice.textContent='Connection unavailable. Reobserve before another action.'}finally{busy=false}}
img.addEventListener('click',e=>{if(!active||busy)return;const b=img.getBoundingClientRect(),x=Math.floor(8*(e.clientX-b.left)/b.width),y=Math.floor(8*(e.clientY-b.top)/b.height);if(x<0||x>7||y<0||y>7)return;const square=String.fromCharCode(97+(white?x:7-x))+(white?8-y:y+1);if(selected===null){selected=square;notice.textContent='Selected '+square;return}const from=selected;selected=null;notice.textContent='';send(document.getElementById('claim-next').checked?'claim_draw':'move',{from,to:square,promotion:document.getElementById('promotion').value})});
document.getElementById('draw').onclick=()=>send('claim_draw');document.getElementById('resign').onclick=()=>send('resign');refresh();setInterval(()=>{if(!busy)refresh()},400);</script></html>'''


def make_server(game, port=0):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_):
            pass  # No raw HTTP/client data to stdout.

        def reply(self, status, body, content_type='application/json', nonce=None):
            if not isinstance(body, (str, bytes)):
                body = json.dumps(body)
            raw = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; img-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'nonce-" + (nonce or '') + "'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def allowed_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def controller(self):
            token = (self.server.game.directory / 'controller-token').read_text()
            return secrets.compare_digest(self.headers.get('X-Controller-Token', ''), token)

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'loopback host required'})
            path = urlsplit(self.path).path
            g = self.server.game
            if path == '/':
                nonce = secrets.token_urlsafe(18)
                white = g.config['orientation'] == 'white'
                files = 'abcdefgh' if white else 'hgfedcba'
                ranks = range(8, 0, -1) if white else range(1, 9)
                body = PAGE.replace('RANKS', ''.join(f'<span>{r}</span>' for r in ranks)).replace('FILES', ''.join(f'<span>{f}</span>' for f in files)).replace('ORIENTATION', str(white).lower()).replace('NONCE', nonce)
                return self.reply(200, body, 'text/html', nonce)
            if path == '/view':
                return self.reply(200, g.public())
            if path == '/board.svg':
                return self.reply(200, g.svg(), 'image/svg+xml')
            if path == '/controller/state' and self.controller():
                return self.reply(200, g.private())
            return self.reply(404, {'error': 'not found'})

        def do_POST(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'loopback host required'})
            fixture = urlsplit(self.path).path == '/controller/action'
            if urlsplit(self.path).path not in {'/action', '/controller/action'}:
                return self.reply(404, {'error': 'not found'})
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if (fixture and not self.controller()) or (not fixture and self.headers.get('Origin') != origin):
                return self.reply(403, {'error': 'origin/controller authorization required'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('bounded JSON body required')
                data = strict_json(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('action object required')
                return self.reply(200, self.server.game.action(data, fixture=fixture))
            except (ValueError, KeyError, TypeError) as exc:
                return self.reply(409, {'error': str(exc)})

    class Server(ThreadingHTTPServer):
        daemon_threads = False
        def service_actions(self):
            if self.game:
                self.game.tick()
    server = Server(('127.0.0.1', port), Handler)
    server.game = game
    return server


def serve(directory, port):
    directory = Path(directory).resolve(strict=True)
    # Cooperative host-wide owner lease. Crash leaves evidence; never steal a stale lease.
    lease = Path(tempfile.gettempdir()) / f'codex-chess-local-board-{os.getuid()}.lock'
    owner = secrets.token_hex(16)
    with lease.open('x') as stream:
        json.dump({'pid': os.getpid(), 'run': str(directory), 'owner': owner}, stream)
    os.chmod(lease, 0o600)
    server = game = None
    retain_lease = False
    try:
        server = make_server(None, port)  # Bind before starting game clocks.
        game = Game(directory)
        server.game = game
        print(json.dumps({'player_url': f'http://127.0.0.1:{server.server_port}/',
                          'controller_token_file': str(directory / 'controller-token')}), flush=True)
        server.serve_forever(poll_interval=.1)
    except EngineExitUnconfirmed:
        retain_lease = True
        raise
    finally:
        try:
            if game:
                game.close()
        finally:
            if server:
                server.server_close()  # Non-daemon handlers drain before ownership ends.
        if not retain_lease and lease.exists() and strict_json(lease.read_bytes()).get('owner') == owner:
            lease.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('directory', type=Path)
    create.add_argument('--config', required=True, type=Path)
    run = sub.add_parser('serve')
    run.add_argument('directory', type=Path)
    run.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if args.command == 'create':
        create_run(args.directory, strict_json(args.config.read_bytes()))
        print(json.dumps({'status': 'prepared_without_clocks', 'directory': str(args.directory)}))
    else:
        serve(args.directory, args.port)


if __name__ == '__main__':
    main()
