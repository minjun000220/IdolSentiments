"""호감도 / 관심도 / 논란도 / 순호감 계산.

대상 인덱스: 0..M-1 = 멤버, M = 그룹 직접 언급

  호감도 (긍정만)
    강도 F = (Σw·p_pos + k·μ) / (Σw + k)          μ = 전체 평균 긍정, k = 사전 강도 (베이지안 보정)
    규모 P = Σw·p_pos
    호감도_m = 100 · [ λ·F_m + (1−λ)·P_m / max P ]

  관심도 = 언급량 (긍정/부정/중립 상관없이 언급된 횟수, 가중치 없음)
    멤버: 관심도_m = 100 · ln(1+N_m) / ln(1+max N)          (그룹 안 1위 = 100)
    그룹: 관심도   = 100 · ln(1+하루 언급 수) / ln(1+기준값)  (절대 점수)

  논란도 = Σw·p_neg / E        순호감 = Σw·(p_pos − p_neg) / E
"""
import numpy as np

EPS = 1e-9


def aggregate(t: np.ndarray, w: np.ndarray, ppos: np.ndarray, pneg: np.ndarray, n_targets: int) -> dict:
    return {
        "N": np.bincount(t, minlength=n_targets).astype(float),
        "W": np.bincount(t, w, minlength=n_targets),
        "POS": np.bincount(t, w * ppos, minlength=n_targets),
        "NEG": np.bincount(t, w * pneg, minlength=n_targets),
    }


def member_favor(agg: dict, n_members: int, cfg: dict) -> np.ndarray:
    W, POS = agg["W"], agg["POS"]
    k, lam = cfg["prior_strength"], cfg["lambda_intensity"]
    mu = POS.sum() / max(W.sum(), EPS)
    F = (POS + k * mu) / (W + k)
    Pm = POS[:n_members]
    return 100 * (lam * F[:n_members] + (1 - lam) * Pm / max(Pm.max(), EPS))


def compute_scores(agg: dict, n_members: int, cfg: dict) -> dict:
    W, POS, NEG, N = agg["W"], agg["POS"], agg["NEG"], agg["N"]
    m, g = slice(0, n_members), n_members
    k, beta = cfg["prior_strength"], cfg["beta_group_direct"]
    mu = POS.sum() / max(W.sum(), EPS)
    F = (POS + k * mu) / (W + k)
    E = POS + NEG

    favor_m = member_favor(agg, n_members, cfg)
    interest_m = 100 * np.log1p(N[m]) / max(np.log1p(N[m].max()), EPS)

    share = W[m] / max(W[m].sum(), EPS)
    member_part = float((share * favor_m).sum())
    group_favor = beta * 100 * F[g] + (1 - beta) * member_part if W[g] > 0 else member_part

    E_tot, NEG_tot, POS_tot = E.sum(), NEG.sum(), POS.sum()
    return {
        "members": {
            "favor": favor_m,
            "interest": interest_m,
            "intensity": 100 * F[m],
            "controversy": NEG[m] / np.maximum(E[m], EPS),
            "net": (POS[m] - NEG[m]) / np.maximum(E[m], EPS),
            "n": N[m],
            "weight": W[m],
            "energy": E[m],
            "share": share,
        },
        "group": {
            "favor": float(group_favor),
            "favor_direct": float(100 * F[g]) if W[g] > 0 else None,
            "favor_members": member_part,
            "controversy": float(NEG_tot / max(E_tot, EPS)),
            "net": float((POS_tot - NEG_tot) / max(E_tot, EPS)),
            "energy": float(E_tot),
            "n": float(N.sum()),
            "n_direct": float(N[g]),
        },
    }


def group_interest(n_mentions: float, days: int, ref_per_day: float) -> tuple[float, float]:
    """그룹 관심도 = 언급량 점수 (다른 그룹과 비교하지 않는 절대 점수).
    → (관심도, 하루 언급 수)"""
    per_day = n_mentions / max(days, 1)
    return float(min(100.0, 100 * np.log1p(per_day) / np.log1p(ref_per_day))), float(per_day)


def quadrant(favor: float, interest: float, favor_mid: float, interest_mid: float, controversy: float) -> str:
    if favor >= favor_mid and interest >= interest_mid:
        return "인기"
    if favor >= favor_mid:
        return "조용한 호감"
    if interest >= interest_mid:
        return "논란 중심" if controversy >= 0.4 else "화제성"
    return "관심 부족"
