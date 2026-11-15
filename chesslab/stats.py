"""Small-sample descriptive statistics. No rating is inferred from bot labels."""
from math import sqrt
from statistics import NormalDist


def wilson(successes: int, total: int, confidence: float = .95) -> tuple[float, float] | None:
    if type(successes) is not int or type(total) is not int or not 0 <= successes <= total:
        raise ValueError('expected integer counts: 0 <= successes <= total')
    if not 0 < confidence < 1:
        raise ValueError('confidence must lie between 0 and 1')
    if total == 0:
        return None
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = successes / total
    d = 1 + z*z / total
    mid = (p + z*z/(2*total)) / d
    half = z * sqrt(p*(1-p)/total + z*z/(4*total*total)) / d
    return max(0, mid-half), min(1, mid+half)


def summarize(runs: list[dict]) -> dict:
    """Summarize one analysis identity, retaining failures in its denominator.

    Seeds vary across replicates. Permission provenance is recorded per run but
    does not define a playing treatment. All current treatment fields must match.
    """
    ids = [r['run'] for r in runs]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate run')
    if any(r['config']['purpose'] == 'synthetic' for r in runs):
        raise ValueError('synthetic fixtures are not experimental evidence')
    identities = {
        (c['condition'], c['model'], c['reasoning'], c['purpose'],
         frozenset(c['capabilities']))
        for c in (r['config'] for r in runs)
    }
    if len(identities) > 1:
        raise ValueError('summarize each analysis identity separately '
                         '(condition, model, reasoning, purpose, capabilities)')
    results = []
    for run in runs:
        endings = [e['payload']['result'] for e in run['events'] if e['kind'] == 'terminal']
        if len(endings) > 1:
            raise ValueError('multiple terminal events')
        results.append(endings[0] if endings else 'incomplete')
    completed = sum(r in {'win', 'loss', 'draw'} for r in results)
    score = sum({'win': 1, 'draw': .5}.get(r, 0) for r in results)
    return {'started': len(runs), 'completed': completed,
            'completion_ci95': wilson(completed, len(runs)),
            'interval_assumption': 'IID Bernoulli games; nominal coverage not established for adaptive opponents',
            'wins': results.count('win'), 'draws': results.count('draw'),
            'losses': results.count('loss'), 'aborted': results.count('aborted'),
            'incomplete': results.count('incomplete'),
            'score_completed': score / completed if completed else None,
            'rating': None}
