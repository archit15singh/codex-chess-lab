"""Create a local, self-contained evidence notebook, never a strength claim."""
import argparse
from html import escape
import io
import json
from pathlib import Path


def _score_text(score: dict) -> str:
    """Keep the engine's score kind and bound flags together when displaying it."""
    values = []
    if score.get('cp') is not None:
        values.append(f"cp {score['cp']}")
    if score.get('mate') is not None:
        values.append(f"mate {score['mate']}")
    bounds = [flag for flag in ('lowerbound', 'upperbound') if score.get(flag)]
    return ('; '.join(values) or 'unavailable') + ' (' + (', '.join(bounds) or 'no bound flag') + ')'


def _difference_status(row: dict) -> str:
    if row.get('cp_loss_raw') is not None:
        return 'finite-search inversion' if row['cp_loss_raw'] < 0 else 'available'
    reasons = []
    for side in ('best', 'selected'):
        score = row[side]
        for flag in ('lowerbound', 'upperbound'):
            if score.get(flag):
                reasons.append(f'{side} {flag}')
        if score.get('mate') is not None:
            reasons.append(f'{side} mate score')
        elif score.get('cp') is None:
            reasons.append(f'missing {side} score')
    return '; '.join(reasons) or 'difference not reported'


def build(evaluation: dict, *, purpose: str, figures: bool = True) -> str:
    if purpose not in {'feasibility', 'pilot', 'heldout'}:
        raise ValueError('explicit experimental purpose required')
    rows = evaluation.get('engine_analysis', {}).get('rows', [])
    chart = ''
    if rows and figures:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        with plt.rc_context({'font.family': 'DejaVu Sans', 'font.size': 10,
                             'axes.facecolor': '#14222d', 'figure.facecolor': '#0c161e',
                             'text.color': '#e1edf4', 'axes.labelcolor': '#e1edf4',
                             'xtick.color': '#afc5d3', 'ytick.color': '#afc5d3',
                             'axes.edgecolor': '#527084', 'svg.fonttype': 'none'}):
            fig, ax = plt.subplots(figsize=(10, 3.8), layout='constrained')
            for side, color in [('white', '#7ce5c2'), ('black', '#ffba83')]:
                selected = [r for r in rows if r['turn'] == side]
                values = [r.get('cp_loss_raw') for r in selected]
                ax.plot([r['ply'] for r in selected],
                        [v if v is not None else float('nan') for v in values],
                        marker='o', markersize=4, linewidth=1.1, color=color,
                        label=side.capitalize())
            ax.axhline(0, color='#527084', linewidth=.8)
            ax.set(xlabel='Game ply', ylabel='Fixed-node search difference (cp)',
                   title='Post-game reference analysis - gaps indicate unavailable cp differences')
            ax.grid(alpha=.15)
            ax.legend(facecolor='#14222d', edgecolor='#527084', labelcolor='#e1edf4')
            buffer = io.BytesIO()
            fig.savefig(buffer, format='svg')
            plt.close(fig)
            chart = buffer.getvalue().decode()
            chart = chart[chart.index('<svg'):]
    table_rows = []
    for row in rows:
        cells = [row['ply'], row['turn'], row['san'], _score_text(row['best']),
                 _score_text(row['selected']), row.get('cp_loss_raw'),
                 _difference_status(row), row.get('bounded_search_inversion')]
        table_rows.append('<tr>' + ''.join('<td>' + escape('unavailable' if c is None else str(c))
                                           + '</td>' for c in cells) + '</tr>')
    engine = evaluation.get('engine_analysis', {})
    summary = {
        'purpose': purpose, 'plies': evaluation['plies'],
        'board terminal': evaluation['board_terminal'],
        'declared result': evaluation['result_header'],
        'board result': evaluation['board_result'],
        'engine': engine.get('engine_id', {}).get('name', 'not run'),
        'nodes per search': engine.get('nodes_per_search', 'not run'),
        'source PGN SHA-256': evaluation['pgn_sha256'],
        'engine binary SHA-256': engine.get('binary_sha256', 'not run'),
    }
    facts = ''.join('<dt>' + escape(k) + '</dt><dd>' + escape(str(v)) + '</dd>'
                    for k, v in summary.items())
    table = ('<div class="scroll"><table><caption>Recorded post-game scores and bound qualifiers</caption>'
             '<thead><tr><th>Ply</th><th>Side</th><th>Move</th><th>Best reference score</th>'
             '<th>Selected-move score</th><th>Raw cp difference</th>'
             '<th>Difference status</th><th>Search inversion</th></tr></thead><tbody>' + ''.join(table_rows) +
             '</tbody></table></div>') if rows else '<p>No engine measurements available.</p>'
    figure_fallback = ('<p>Figure omitted; the table retains the recorded measurements.</p>'
                       if rows and not figures else '<p>No engine figure is available.</p>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex Chess Research - Evidence notebook</title><style>
:root{color-scheme:dark;background:#0c161e;color:#e1edf4;font:17px/1.65 system-ui,sans-serif}
body{max-width:1100px;margin:auto;padding:4vw}h1{font-size:clamp(2rem,5vw,3.6rem);line-height:1.12;max-width:19ch}
h2{margin-top:2.6rem}p{max-width:77ch}.eyebrow{letter-spacing:.13em;text-transform:uppercase;color:#7ce5c2;font-size:.8rem}
.notice{border-left:3px solid #ffba83;padding:1rem 1.4rem;background:#19222a;border-radius:4px}
dl{display:grid;grid-template-columns:minmax(150px,1fr) 3fr;gap:.5rem 1rem}dt{color:#afc5d3}dd{margin:0;overflow-wrap:anywhere}
figure{margin:2rem 0}svg{width:100%;height:auto}figcaption,caption{color:#afc5d3;font-size:.85rem;text-align:left}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:.85rem}td,th{padding:.5rem;text-align:left;border-bottom:1px solid #304352}
th{color:#7ce5c2}footer{border-top:1px solid #304352;margin-top:3rem;padding-top:1rem;color:#afc5d3;font-size:.85rem}
@media(max-width:600px){dl{grid-template-columns:1fr}dd{margin-bottom:.8rem}}@media print{body{padding:0}thead{display:table-header-group}tr{break-inside:avoid}*{print-color-adjust:exact}}</style>
<main><p class="eyebrow">Private research notebook / actual evidence</p><h1>Chess decisions through a browser</h1>
<p class="notice"><strong>Work in progress. No strength or grandmaster-level estimate.</strong>
This notebook presents one evidence file. Feasibility, pilot and held-out records must remain separate.
It is not the final research paper or a substitute for the full completion audit.</p>
<h2>Evidence identity</h2><dl>''' + facts + '''</dl>
<h2>What this measurement can establish</h2><p>Legal post-game replay establishes consistency of the submitted move sequence.
A board-terminal result can verify the recorded ending. File hashes verify referenced bytes; they do not establish
screenshot meaning, completeness of the host trace, absence of assistance, or opponent calibration. Independent visual
and tool-trace audits are required.</p>
<figure>''' + (chart or figure_fallback) + '''<figcaption>Reference scores come from two separately reset searches at the same pre-move position and moving-side perspective.
Finite search may yield negative differences; these are retained as search inversions. Mate distances and bounded or
missing scores are not converted into centipawns. The table retains each score's bound flags; no bound flag is not
a guarantee of exact chess value. This plot is not an Elo estimate.</figcaption></figure>
''' + table + '''<h2>Remaining research requirements</h2><p>A frozen baseline pilot, controlled ablations, calibrated comparisons,
held-out reflection tests and full reproducibility checks remain necessary. Adaptive Oscar account history may make games
dependent. Human validation needs disclosed consenting opponents and authorization. No results are published by generating this local file.</p>
</main><footer>Generated from recorded evaluator JSON. Figures and table use the same input rows. Keep raw account and participant data private.</footer></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evaluation', type=Path)
    parser.add_argument('--purpose', required=True, choices=['feasibility', 'pilot', 'heldout'])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    html = build(json.loads(args.evaluation.read_text()), purpose=args.purpose)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(html)
    print(args.output.resolve())


if __name__ == '__main__':
    main()
