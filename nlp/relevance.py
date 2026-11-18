import numpy as np


class RelevanceScorer:
    """멤버/그룹 이름 없이 '맥락'으로만 연결된 문장이 실제로 아이돌 얘기인지 0~1 점수."""

    def __init__(self, encoder, anchors: list[str], low: float, high: float):
        self.ref = encoder.encode(anchors)
        self.low, self.high = low, high

    def score(self, emb: np.ndarray) -> np.ndarray:
        if len(emb) == 0:
            return np.zeros(0, dtype=np.float32)
        sim = (emb @ self.ref.T).max(axis=1)
        return np.clip((sim - self.low) / (self.high - self.low), 0.0, 1.0)
