import numpy as np

from scoring.metrics import aggregate, member_favor


def bootstrap_ranks(t, w, ppos, pneg, n_members: int, cfg: dict) -> dict:
    """대상별로 언급을 복원추출해 호감도 순위를 반복 계산 → 95% 순위 구간, 호감도 신뢰구간."""
    rng = np.random.default_rng(cfg.get("seed", 42))
    B = cfg["bootstrap"]
    n_targets = n_members + 1
    groups = [np.where(t == i)[0] for i in range(n_targets)]
    ranks = np.zeros((B, n_members), dtype=int)
    favors = np.zeros((B, n_members))
    for b in range(B):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups if len(g)] or [np.array([], int)])
        agg = aggregate(t[idx], w[idx], ppos[idx], pneg[idx], n_targets)
        f = member_favor(agg, n_members, cfg)
        favors[b] = f
        ranks[b] = (-f).argsort().argsort() + 1
    return {
        "rank_lo": np.percentile(ranks, 2.5, axis=0).round().astype(int),
        "rank_hi": np.percentile(ranks, 97.5, axis=0).round().astype(int),
        "favor_lo": np.percentile(favors, 2.5, axis=0),
        "favor_hi": np.percentile(favors, 97.5, axis=0),
    }
