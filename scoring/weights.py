import numpy as np


def mention_weights(source: np.ndarray, likes: np.ndarray, age_days: np.ndarray, conf: np.ndarray,
                    relevance: np.ndarray, cfg: dict) -> np.ndarray:
    """w_i = s_src × (1 + ln(1+likes)) × 0.5^(age/반감기) × conf × relevance"""
    s_src = np.array([cfg["source_weight"].get(s, 1.0) for s in source], dtype=np.float64)
    like_w = 1.0 + np.log1p(np.maximum(likes, 0))
    decay = 0.5 ** (age_days / cfg["half_life_days"])
    return s_src * like_w * decay * conf * relevance
