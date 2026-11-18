"""복붙/도배 제거.

짧은 문장("민지 예쁘다")은 여러 사람이 같은 말을 하는 게 정상이므로 지우지 않는다.
긴 문장이 거의 똑같이 반복되는 경우(총공 문구, 봇, 도배)만 SBERT 유사도로 제거.
"""
import numpy as np


def near_duplicate_mask(emb: np.ndarray, lengths: np.ndarray, threshold: float = 0.95,
                        min_len: int = 20, max_n: int = 30000, block: int = 2048) -> np.ndarray:
    """True = 유지. 앞에 나온 문장과 유사도 >= threshold 인 긴 문장은 False."""
    keep = np.ones(len(emb), dtype=bool)
    idx = np.where(lengths >= min_len)[0]
    if len(idx) < 2 or len(idx) > max_n:
        return keep
    E = emb[idx]
    for start in range(0, len(idx), block):
        sims = E[start:start + block] @ E.T            # (b, n)
        for r in range(sims.shape[0]):
            i = start + r
            if i == 0:
                continue
            if (sims[r, :i] >= threshold).any():
                keep[idx[i]] = False
    return keep
