# Claude vs Codex in Duolingo Chess

The controller plays a prearranged friend match between two accounts on one
Mac mini. You start the challenge and accept it yourself. Claude and Codex
then choose moves independently from cropped screenshots. The controller
sends their clicks to the assigned Brave tab through Playwright. Neither
player receives the page DOM, a chess engine, or access to the macOS pointer.

The controller reserves each move in a private log before clicking. It waits
for the board pixels to settle and asks the other provider in a separate
vision request to confirm the visible move and turn change before continuing.
A changed board alone does not count as verification. If a click fails, a
tab navigates, or verification is unclear, the run stops without retrying.

## Offline checks

Requires Node.js 22 or later. The test suite uses simulated screenshots,
browser objects, and API responses.

```sh
npm --prefix scripts/friend-match ci --ignore-scripts
npm --prefix scripts/friend-match test
node scripts/friend-match/cli.mjs --check configs/friend-match.example.json
```

## Setup for a future match

1. Confirm permission to automate this private friend match under
   [Duolingo's terms](https://www.duolingo.com/terms). This controller starts from
   an already-open friend game with both sides visible in Brave. Verify the
   friend challenge is available to both accounts on the web before setting up
   a run. The controller assumes White moves first. Duolingo documents
   [friend invitations](https://blog.duolingo.com/chess-course/).
2. Start two dedicated Brave instances. Keep each debugging port on loopback
   and use separate data directories. Reuse these directories for this setup
   so each instance retains only its own test account.

   ```sh
   open -na 'Brave Browser' --args --user-data-dir="$HOME/.chesslab-brave-white" --remote-debugging-address=127.0.0.1 --remote-debugging-port=9225
   open -na 'Brave Browser' --args --user-data-dir="$HOME/.chesslab-brave-black" --remote-debugging-address=127.0.0.1 --remote-debugging-port=9226
   ```

3. Sign in once per instance and add the accounts as friends. Prepare the
   configuration before starting a timed game. Copy
   [the example configuration](../configs/friend-match.example.json) into
   `evidence/private/`. Replace each example endpoint with the
   `webSocketDebuggerUrl` returned by the instance's
   `http://127.0.0.1:PORT/json/version`, and use each match tab's exact URL.
   Each instance must have exactly one tab with that URL.
4. Set browser zoom to 100% and keep the window size and scroll position
   fixed. Measure `board` as the outer boundaries of the 8×8 playing area in
   viewport CSS pixels. Measure `view` as a rectangle containing the board,
   visible turn indicator, promotion controls, and result UI. Use the
   viewport's top-left as the origin and keep the crop at most 1024×1024.
   Avoid account details in the crop. Provider calls send these cropped
   images to [Anthropic](https://platform.claude.com/docs/en/build-with-claude/vision)
   and [OpenAI](https://developers.openai.com/api/docs/guides/images-vision).
5. Set `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in the shell. The example uses
   Claude Sonnet 4.6 and GPT-5.3-Codex through their paid vision APIs.
   Choose image-capable model IDs available to your accounts. GPT-5.3-Codex
   is scheduled to retire on April 1, 2027. OpenAI lists GPT-6 Sol as its
   [replacement](https://developers.openai.com/api/docs/deprecations). Provider
   requests can take up to 45 seconds apiece, so allow time on the game clock
   for both move selection and visual verification.
6. Freeze and verify the runtime before starting the challenge. Run
   these commands from the repository root.

   ```sh
   match_snapshot=evidence/private/frozen-friend-match
   python3 -m chesslab.freeze "$match_snapshot" --friend-match
   python3 -m chesslab.freeze "$match_snapshot" --check
   npm --prefix "$match_snapshot/scripts/friend-match" ci --ignore-scripts
   node "$match_snapshot/scripts/friend-match/cli.mjs" --check evidence/private/friend-match.json
   ```

7. Start and accept the friend challenge, confirm the White and Black
   assignments and board geometry on both tabs, then explicitly start the
   controller. Leave the dedicated tabs alone during the match.

   ```sh
   node "$match_snapshot/scripts/friend-match/cli.mjs" --live-friend-match evidence/private/friend-match.json
   ```

The controller writes screenshots and a JSONL journal under the frozen runtime's
`evidence/private/`. Keep that evidence and configuration local. A per-user lock
prevents two copies of this controller from running together. After an
interruption, inspect the live boards and the last recorded intent before any
further input. If a lock remains, leave it in place until you have confirmed the
old controller is stopped. The controller does not resume a partial game.

The browser integration uses [Playwright's CDP connection](https://playwright.dev/docs/api/class-browsertype#browser-type-connect-over-cdp)
and [viewport-relative mouse input](https://playwright.dev/docs/api/class-mouse).
The live Duolingo friend UI, click handling, and provider responses have yet to
be tested together.
