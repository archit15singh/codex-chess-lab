"""Synthetic engineering fixtures only; no model games or real engine queries."""
from contextlib import contextmanager
import hashlib
from concurrent.futures import Future
import http.client
import json
import re
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

import chess
from chesslab.local_board import Game, create_run, make_server, strict_json, serve, PAGE, EngineOpponent, EngineExitUnconfirmed


class Clock:
    def __init__(self): self.value = 0
    def __call__(self): return self.value


def config(fen=chess.STARTING_FEN, **changes):
    return {'mode': 'manual_fixture', 'start_fen': fen, 'player_color': 'white',
            'orientation': 'white', 'decision_seconds': 90, 'wall_seconds': 3600,
            'engine': None, **changes}


class FakeOpponent:
    identity = {'engine_id': {'name': 'Synthetic fixture only'}}
    def __init__(self, _): pass
    def move(self, board): return next(iter(board.legal_moves))
    def close(self): pass


class BoardFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0
        self.clock = Clock()

    def game(self, value=None, factory=FakeOpponent):
        self.counter += 1
        path = self.root / str(self.counter)
        create_run(path, value or config())
        game = Game(path, clock=self.clock, engine_factory=factory)
        self.addCleanup(game.close)
        return game

    def move(self, game, uci, *, fixture=True, identity=None, version=None):
        return game.action({'intent_id': identity or f'intent-{len(game.board.move_stack)}-{game.sequence}',
            'version': game.version if version is None else version, 'kind': 'move',
            'from': uci[:2], 'to': uci[2:4], 'promotion': uci[4:] or 'q'}, fixture=fixture)

    def controlled(self, **changes):
        return config(mode='controlled', engine={'path': sys.executable, 'options': {'Threads': 1},
                 'nodes': 100, 'movetime_ms': None, 'timeout_seconds': 2}, **changes)


class BoardTests(BoardFixture, unittest.TestCase):
    def test_active_engine_segments_include_startup_search_cleanup_not_idle(self):
        with patch('chesslab.local_board.time.monotonic_ns', side_effect=[100, 110, 200, 230, 300, 340]):
            g = self.game(self.controlled())
            self.clock.value = 12  # Waiting for the player is not an engine segment.
            self.move(g, 'e2e4', fixture=False)
            g.worker.join(timeout=2)
            self.assertFalse(g.worker.is_alive())
            self.clock.value = 25
            g.close()
        segments = [e for e in map(json.loads, (g.directory / 'events.jsonl').read_text().splitlines())
                    if e['kind'] == 'engine_active_segment']
        self.assertEqual([(e['phase'], e['active_ns']) for e in segments],
                         [('startup', 10), ('search', 30), ('cleanup', 40)])

    def test_failed_search_still_has_exactly_one_measured_segment(self):
        class Broken(FakeOpponent):
            def move(self, board): raise ValueError('synthetic failure')
        with patch('chesslab.local_board.time.monotonic_ns', side_effect=[100, 110, 200, 230, 300, 340]):
            g = self.game(self.controlled(player_color='black'), factory=Broken)
            g.worker.join(timeout=2)
            self.assertFalse(g.worker.is_alive())
            g.close()
        events = list(map(json.loads, (g.directory / 'events.jsonl').read_text().splitlines()))
        segments = [e for e in events if e['kind'] == 'engine_active_segment']
        self.assertEqual([(e['phase'], e['active_ns']) for e in segments],
                         [('startup', 10), ('search', 30), ('cleanup', 40)])
        self.assertEqual(g.reason, 'opponent_error')

    def test_prepare_freezes_without_clocks_and_refuses_overwrite(self):
        path = self.root / 'prepared'
        create_run(path, config())
        self.assertFalse((path / 'events.jsonl').exists())
        self.assertFalse((path / 'state.json').exists())
        with self.assertRaises(FileExistsError): create_run(path, config())
        self.assertEqual((path / 'controller-token').stat().st_mode & 0o777, 0o600)

    def test_invalid_fen_budget_or_missing_engine_rejected(self):
        for value in [config('8/8/8/8/8/8/8/8 w - - 0 1'), config(decision_seconds=float('nan')),
                      self.controlled() | {'engine': {'path': '/NO_SUCH_ENGINE', 'options': {}, 'nodes': 1, 'movetime_ms': None, 'timeout_seconds': 2}}]:
            with self.subTest(value=value), self.assertRaises((ValueError, FileNotFoundError)):
                create_run(self.root / 'invalid', value)
        v = self.controlled();v['engine']['movetime_ms'] = 10
        with self.assertRaises(ValueError): create_run(self.root / 'invalid', v)

    def test_changed_frozen_config_refuses_start(self):
        path = self.root / 'tampered';create_run(path, config())
        with (path / 'config.json').open('a') as f: f.write(' ')
        with self.assertRaises(ValueError): Game(path)

    def test_legal_moves_illegal_attempt_and_out_of_turn(self):
        g = self.game()
        with self.assertRaisesRegex(ValueError, 'illegal'): self.move(g, 'e2e5', fixture=False)
        self.move(g, 'e2e4', fixture=False)
        with self.assertRaisesRegex(ValueError, 'not player turn'): self.move(g, 'e7e5', fixture=False)
        self.assertEqual(g.board.piece_at(chess.E4), chess.Piece(chess.PAWN, chess.WHITE))
        self.assertEqual(len(g.board.move_stack), 1)

    def test_duplicate_intent_and_stale_version_cannot_apply_twice(self):
        g = self.game();self.move(g, 'e2e4', identity='fixed')
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.move(g, 'e7e5', identity='fixed')
        with self.assertRaisesRegex(ValueError, 'stale'): self.move(g, 'e7e5', version=0)
        self.assertEqual(len(g.board.move_stack), 1)

    def test_castling_both_sides(self):
        g = self.game(config('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'))
        self.move(g, 'e1g1');self.move(g, 'e8c8')
        self.assertEqual(g.board.piece_at(chess.F1).piece_type, chess.ROOK)
        self.assertEqual(g.board.piece_at(chess.D8).piece_type, chess.ROOK)

    def test_en_passant_uses_actual_move_history(self):
        g = self.game()
        for move in ['e2e4', 'a7a6', 'e4e5', 'd7d5', 'e5d6']: self.move(g, move)
        self.assertIsNone(g.board.piece_at(chess.D5))
        self.assertEqual(g.board.piece_at(chess.D6), chess.Piece(chess.PAWN, chess.WHITE))

    def test_all_four_promotions(self):
        for choice in 'qrbn':
            g = self.game(config('7k/P7/8/8/8/8/8/7K w - - 0 1'))
            self.move(g, 'a7a8' + choice)
            self.assertEqual(g.board.piece_at(chess.A8).symbol(), choice.upper())

    def test_checkmate_and_no_moves_terminal_start(self):
        g = self.game()
        for move in ['f2f3', 'e7e5', 'g2g4', 'd8h4']: self.move(g, move)
        self.assertEqual((g.reason, g.result), ('checkmate', '0-1'))
        with self.assertRaisesRegex(ValueError, 'ended'): self.move(g, 'a2a3')
        h = self.game(config('7k/5K2/6Q1/8/8/8/8/8 b - - 0 1'))
        self.assertEqual((h.reason, h.result), ('stalemate', '1/2-1/2'))

    def test_fifty_move_claim_current_and_announced_move(self):
        for halfmove, extra in [(100, {}), (99, {'from': 'a1', 'to': 'b1', 'promotion': 'q'})]:
            g = self.game(config(f'8/8/8/8/8/4k3/8/R3K3 w - - {halfmove} 76'))
            g.action({'intent_id': 'claim', 'version': g.version, 'kind': 'claim_draw', **extra})
            self.assertEqual((g.reason, g.result), ('claimed_draw', '1/2-1/2'))
            self.assertEqual(len(g.board.move_stack), 0)

    def test_threefold_claim_and_automatic_fivefold(self):
        for cycles in [2, 4]:
            g = self.game()
            for _ in range(cycles):
                for move in ['g1f3', 'g8f6', 'f3g1', 'f6g8']: self.move(g, move)
            if cycles == 2:
                g.action({'intent_id': 'claim', 'version': g.version, 'kind': 'claim_draw'})
                self.assertEqual(g.reason, 'claimed_draw')
            else: self.assertEqual(g.reason, 'fivefold_repetition')

    def test_unjustified_draw_and_resignation(self):
        g = self.game()
        with self.assertRaisesRegex(ValueError, 'not claimable'):
            g.action({'intent_id': 'bad-draw', 'version': 0, 'kind': 'claim_draw'})
        g.action({'intent_id': 'resign', 'version': 0, 'kind': 'resign'})
        self.assertEqual((g.reason, g.result), ('resignation', '0-1'))

    def test_decision_and_wall_timeout_equality_not_board_loss(self):
        for value, elapsed, reason in [(config(), 90, 'decision_timeout'), (config(wall_seconds=10), 10, 'wall_timeout')]:
            self.clock.value = 0;g = self.game(value);self.clock.value = elapsed;g.tick()
            self.assertEqual((g.reason, g.result), (reason, '*'))
            self.assertEqual(json.loads((g.directory / 'state.json').read_text())['reason'], reason)

    def test_engine_reply_is_opponent_only_and_restarts_player_clock(self):
        g = self.game(self.controlled());self.clock.value = 20;self.move(g, 'e2e4', fixture=False)
        g.worker.join(timeout=2)
        self.assertEqual(len(g.board.move_stack), 2)
        self.assertTrue(g.public()['your_turn'])
        self.assertEqual(g.public()['decision_remaining_seconds'], 90)
        self.assertNotIn('engine', g.public())
        with self.assertRaisesRegex(ValueError, 'fixture actions disabled'):
            self.move(g, 'd2d4', fixture=True)

    def test_engine_handles_black_player_first_and_no_move_failure(self):
        g = self.game(self.controlled(player_color='black'));g.worker.join(timeout=2)
        self.assertEqual(len(g.board.move_stack), 1)
        class Empty(FakeOpponent):
            def move(self, board): return None
        h = self.game(self.controlled(), Empty);self.move(h, 'e2e4', fixture=False);h.worker.join(timeout=2)
        self.assertEqual((h.reason, h.result), ('opponent_error', '*'))

    def test_late_engine_result_does_not_mutate_timed_out_board(self):
        release = threading.Event()
        class Slow(FakeOpponent):
            def move(self, board): release.wait(2);return next(iter(board.legal_moves))
        g = self.game(self.controlled(wall_seconds=10), Slow);self.move(g, 'e2e4', fixture=False)
        self.clock.value = 10;g.tick();release.set();g.worker.join(timeout=2)
        self.assertEqual(len(g.board.move_stack), 1)
        self.assertEqual(g.reason, 'wall_timeout')

    def test_private_evidence_hash_chain_and_no_resume(self):
        g = self.game();self.move(g, 'e2e4')
        previous = None
        for line in (g.directory / 'events.jsonl').read_text().splitlines():
            event = json.loads(line);self.assertEqual(event['previous_sha256'], previous)
            previous = hashlib.sha256(line.encode()).hexdigest()
        self.assertEqual(g.private()['event_sha256'], previous)
        with self.assertRaises(FileExistsError): Game(g.directory)

    def test_existing_host_owner_never_stolen(self):
        lease = self.root / ('codex-chess-local-board-' + str(__import__('os').getuid()) + '.lock')
        lease.write_text('{"owner":"prior"}')
        with patch('chesslab.local_board.tempfile.gettempdir', return_value=str(self.root)), patch('chesslab.local_board.make_server') as server:
            with self.assertRaises(FileExistsError): serve(self.root, 0)
            server.assert_not_called()
        self.assertEqual(lease.read_text(), '{"owner":"prior"}')

    def test_bind_failure_starts_no_game_clock_and_releases_own_lease(self):
        with patch('chesslab.local_board.tempfile.gettempdir', return_value=str(self.root)), patch('chesslab.local_board.make_server', side_effect=OSError('synthetic bind failure')), patch('chesslab.local_board.Game') as game:
            with self.assertRaises(OSError): serve(self.root, 0)
            game.assert_not_called()
        self.assertFalse(list(self.root.glob('*.lock')))

    def test_engine_binary_tamper_preserves_startup_failure(self):
        path = self.root / 'fake-engine';path.write_text('synthetic executable, never run');path.chmod(0o700)
        value = self.controlled();value['engine']['path'] = str(path)
        run = self.root / 'changed-engine';create_run(run, value);path.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'engine binary'): Game(run, engine_factory=FakeOpponent)
        self.assertIn('startup_failure', (run / 'events.jsonl').read_text())
        with self.assertRaises(FileExistsError): Game(run, engine_factory=FakeOpponent)

    def test_unproven_worker_shutdown_keeps_evidence_open(self):
        release = threading.Event()
        class Blocked(FakeOpponent):
            def move(self, board): release.wait(2);return next(iter(board.legal_moves))
        g = self.game(self.controlled(), Blocked);self.move(g, 'e2e4', fixture=False)
        try:
            with self.assertRaisesRegex(TimeoutError, 'worker still alive'): g.close(join_timeout=.01)
            self.assertFalse(g.journal.closed)
            self.assertIn('shutdown_blocked', (g.directory / 'events.jsonl').read_text())
        finally:
            release.set();g.worker.join(timeout=2)
        g.close();self.assertTrue(g.journal.closed)

    def test_unproven_close_preserves_global_owner_lease(self):
        class FakeServer:
            server_port = 1234
            def serve_forever(self, **_): pass
            def server_close(self): pass
        class BlockedGame:
            def close(self): raise TimeoutError('synthetic worker remains')
        with patch('chesslab.local_board.tempfile.gettempdir', return_value=str(self.root)), patch('chesslab.local_board.make_server', return_value=FakeServer()), patch('chesslab.local_board.Game', return_value=BlockedGame()):
            with self.assertRaises(TimeoutError): serve(self.root, 0)
        leases = list(self.root.glob('*.lock'));self.assertEqual(len(leases), 1)
        self.assertIn('owner', json.loads(leases[0].read_text()))

    def test_browser_click_geometry_white_black_and_promotion(self):
        node = shutil.which('node')
        if node is None: self.skipTest('Node required for browser-script fixture')
        script = re.search(r'<script nonce="NONCE">(.*?)</script>', PAGE, re.S)[1]
        setup = r"""const sent=[];const elements={};for(const id of ['board','notice','status','promotion','claim-next','draw','resign'])elements[id]={textContent:'',value:'n',checked:false,addEventListener:(event,fn)=>elements[id].click=fn,getBoundingClientRect:()=>({left:100,top:50,width:640,height:640})};globalThis.document={getElementById:id=>elements[id]};globalThis.setInterval=()=>{};Object.defineProperty(globalThis,'crypto',{value:{randomUUID:()=> 'synthetic-intent'}});globalThis.fetch=async(url,opts)=>{if(opts&&opts.body)sent.push(JSON.parse(opts.body));return {ok:true,json:async()=>({version:0,your_turn:true,message:'Your turn',decision_remaining_seconds:90,status:'running'})}};"""
        for orientation, x, expected in [('true',460,('e2','e4')),('false',380,('e7','e5'))]:
            checks = f"""(async()=>{{await new Promise(setImmediate);elements.board.click({{clientX:{x},clientY:570}});elements.board.click({{clientX:{x},clientY:410}});await new Promise(setImmediate);const r=sent[0];if(sent.length!==1||r.from!=={json.dumps(expected[0])}||r.to!=={json.dumps(expected[1])}||r.promotion!=='n'||r.version!==0)throw Error('native click mapping');}})().catch(e=>{{console.error(e.message);process.exitCode=1}});"""
            result = subprocess.run([node,'-e',setup+script.replace('ORIENTATION',orientation)+checks],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_idle_engine_unconfirmed_close_keeps_journal_for_retry(self):
        finished = threading.Event()
        class Idle(FakeOpponent):
            def close(self):
                if not finished.is_set(): raise EngineExitUnconfirmed('synthetic pending process')
                return 0
        g = self.game(self.controlled(), Idle)
        with self.assertRaises(EngineExitUnconfirmed): g.close()
        self.assertFalse(g.journal.closed)
        finished.set();g.close();self.assertTrue(g.journal.closed)

    def test_closed_game_rejects_without_writing_closed_journal(self):
        g = self.game();g.close();path = g.directory / 'events.jsonl';before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'server closed'):
            g.action({'intent_id':'after-stop','version':g.version,'kind':'resign'})
        g.tick();self.assertEqual(path.read_bytes(), before)

    def test_unconfirmed_startup_preserves_owner(self):
        class FakeServer:
            server_port = 1234
            def server_close(self): pass
        with patch('chesslab.local_board.tempfile.gettempdir',return_value=str(self.root)), patch('chesslab.local_board.make_server',return_value=FakeServer()), patch('chesslab.local_board.Game',side_effect=EngineExitUnconfirmed('synthetic startup')):
            with self.assertRaises(EngineExitUnconfirmed): serve(self.root,0)
        self.assertEqual(len(list(self.root.glob('*.lock'))),1)

    def test_duplicate_JSON_keys_reject(self):
        with self.assertRaises(ValueError): strict_json('{"kind":"move","kind":"resign"}')



class EngineShutdownTests(unittest.TestCase):
    def test_unconfirmed_actual_process_exit_cannot_return_success(self):
        class Process:
            returncode = Future()
            def close(self): pass  # Exactly the asynchronous transport-close seam.
        opponent = object.__new__(EngineOpponent);opponent.worker = Process()
        with self.assertRaises(TimeoutError): opponent.close()

    def test_resolved_process_exit_is_proven_even_without_move_thread(self):
        class Process:
            returncode = Future()
            def close(self): pass
        Process.returncode.set_result(-9)
        opponent = object.__new__(EngineOpponent);opponent.worker = Process()
        self.assertEqual(opponent.close(), -9)



    def test_configure_failure_closes_and_proves_process_exit(self):
        worker=Mock();worker.configure.side_effect=ValueError('synthetic configure');worker.returncode=Future();worker.returncode.set_result(-9)
        with patch('chesslab.local_board.chess.engine.SimpleEngine.popen_uci',return_value=worker):
            with self.assertRaises(ValueError): EngineOpponent({'path':'NOT_RUN','timeout_seconds':1,'options':{}})
        worker.close.assert_called_once();self.assertTrue(worker.returncode.done())

    def test_startup_and_cleanup_interrupts_cannot_release_unproven_owner(self):
        with patch('chesslab.local_board.chess.engine.SimpleEngine.popen_uci',side_effect=KeyboardInterrupt):
            with self.assertRaises(EngineExitUnconfirmed): EngineOpponent({'path':'NOT_RUN','timeout_seconds':1})
        opponent=object.__new__(EngineOpponent);opponent.worker=Mock();opponent.worker.close.side_effect=KeyboardInterrupt
        with self.assertRaises(EngineExitUnconfirmed): opponent.close()


class HTTPTests(BoardFixture, unittest.TestCase):
    # Keep transport checks separate from the synthetic rule fixtures above.
    @contextmanager
    def server(self):
        g = self.game();server = make_server(g);thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        try: yield g, server
        finally: server.shutdown();server.server_close();thread.join()

    def request(self, server, method, path, value=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
        body = json.dumps(value) if value is not None else None
        base = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{server.server_port}'}
        connection.request(method, path, body=body, headers={**base, **(headers or {})});response = connection.getresponse();data = response.read();status = response.status;connection.close();return status, data

    def test_only_visual_state_served_and_private_token_required(self):
        with self.server() as (g, server):
            for path in ['/', '/view', '/board.svg']:
                status, data = self.request(server, 'GET', path)
                self.assertEqual(status, 200);self.assertNotIn(g.board.fen().encode(), data)
                self.assertNotIn(b'legal_moves', data);self.assertNotIn(b'engine_identity', data)
            self.assertEqual(self.request(server, 'GET', '/controller/state')[0], 404)
            token = (g.directory / 'controller-token').read_text()
            status, data = self.request(server, 'GET', '/controller/state', headers={'X-Controller-Token': token})
            self.assertEqual(status, 200);self.assertIn('fen', json.loads(data))
            self.assertEqual(self.request(server, 'GET', '/config.json')[0], 404)

    def test_http_handlers_drain_and_cannot_write_after_game_close(self):
        with self.server() as (g, server):
            entered,release,closed=threading.Event(),threading.Event(),threading.Event();original=g.action;result=[]
            def pending(*args,**kwargs): entered.set();release.wait(2);return original(*args,**kwargs)
            def client(): result.append(self.request(server,'POST','/action',{'intent_id':'pending','version':0,'kind':'resign'})[0])
            with patch.object(g,'action',side_effect=pending):
                thread=threading.Thread(target=client);thread.start();self.assertTrue(entered.wait(1));g.close();server.shutdown()
                drainer=threading.Thread(target=lambda:(server.server_close(),closed.set()));drainer.start()
                try: self.assertFalse(closed.wait(.01))
                finally: release.set()
                thread.join(2);drainer.join(2);self.assertTrue(closed.is_set());self.assertEqual(result,[409])

    def test_transport_origin_host_duplicate_and_fixture_auth(self):
        with self.server() as (g, server):
            action = {'intent_id': 'HTTP-1', 'version': 0, 'kind': 'move', 'from': 'e2', 'to': 'e4'}
            self.assertEqual(self.request(server, 'POST', '/action', action, {'Origin': 'https://elsewhere.invalid'})[0], 403)
            self.assertEqual(self.request(server, 'GET', '/', headers={'Host': 'elsewhere.invalid'})[0], 403)
            self.assertEqual(self.request(server, 'POST', '/controller/action', action)[0], 403)
            self.assertEqual(self.request(server, 'POST', '/action', action)[0], 200)
            self.assertEqual(self.request(server, 'POST', '/action', action)[0], 409)
            self.assertEqual(len(g.board.move_stack), 1)


if __name__ == '__main__': unittest.main()
