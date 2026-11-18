"""감성 확률 (neg, neu, pos).

1) AnchorSentiment: 라벨 데이터 없이 시작. 문장 임베딩과 앵커 문장들의 코사인 유사도 →
   클래스별 상위 k개 평균 → softmax(s / τ)
2) SetFitSentiment: training/train_setfit.py 로 학습한 모델이 있으면 자동 사용 (권장)
"""
import json
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

LABELS = ("neg", "neu", "pos")
ANCHOR_KEYS = {"neg": "negative", "neu": "neutral", "pos": "positive"}


def softmax(x: np.ndarray, axis=-1) -> np.ndarray:
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


class AnchorSentiment:
    name = "anchor"

    def __init__(self, encoder, anchors: dict, topk: int = 3, temperature: float = 0.05):
        self.encoder = encoder
        self.topk = topk
        self.tau = temperature
        self.anchor_emb = {lab: encoder.encode(anchors[ANCHOR_KEYS[lab]]) for lab in LABELS}

    def predict(self, texts: list[str], emb: np.ndarray) -> np.ndarray:
        scores = []
        for lab in LABELS:
            sims = emb @ self.anchor_emb[lab].T                     # (n, a)
            k = min(self.topk, sims.shape[1])
            top = np.sort(sims, axis=1)[:, -k:]
            scores.append(top.mean(axis=1))
        return softmax(np.stack(scores, axis=1) / self.tau)


class SetFitSentiment:
    name = "setfit"

    def __init__(self, path: str | Path):
        from setfit import SetFitModel
        self.model = SetFitModel.from_pretrained(str(path))
        meta = Path(path) / "label_map.json"
        self.label_order = json.loads(meta.read_text())["labels"] if meta.exists() else list(LABELS)

    def predict(self, texts: list[str], emb: np.ndarray | None = None) -> np.ndarray:
        proba = self.model.predict_proba(texts)
        proba = proba.cpu().numpy() if hasattr(proba, "cpu") else np.asarray(proba)
        classes = list(getattr(self.model.model_head, "classes_", range(proba.shape[1])))
        out = np.zeros((len(texts), 3), dtype=np.float32)
        for col, cls in enumerate(classes):
            lab = self.label_order[int(cls)] if not isinstance(cls, str) else cls
            out[:, LABELS.index(lab)] = proba[:, col]
        return out


def build_sentiment(settings: dict, encoder, anchors: dict, root: Path):
    path = root / settings["model"]["setfit_path"]
    if path.exists():
        try:
            log.info("SetFit 감성 모델 사용: %s", path)
            return SetFitSentiment(path)
        except Exception as e:
            log.warning("SetFit 로딩 실패 (%s) → 앵커 방식 사용", e)
    log.info("앵커 기반 zero-shot 감성 분석 사용 (라벨링 후 SetFit 학습 권장)")
    n = settings["nlp"]
    return AnchorSentiment(encoder, anchors, n["anchor_topk"], n["temperature"])
