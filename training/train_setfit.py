"""SetFit 학습: SBERT를 대조학습으로 미세조정 + 분류 헤드.
클래스당 50~100개 라벨이면 앵커 방식보다 확실히 좋아진다.

학습 후 models/setfit-sentiment 에 저장되며, analyze 실행 시 자동으로 사용된다.
"""
import csv
import json
import logging
import random

import numpy as np

from core.config import ROOT, load_anchors
from nlp.sentiment import LABELS, AnchorSentiment

log = logging.getLogger(__name__)


def train(settings: dict, db=None) -> None:
    try:
        from datasets import Dataset
        from setfit import SetFitModel, Trainer, TrainingArguments
        from sklearn.metrics import classification_report, f1_score
    except ImportError:
        raise SystemExit("pip install setfit datasets scikit-learn 후 다시 실행하세요.")

    path = ROOT / settings["training"]["labels_path"]
    if not path.exists():
        raise SystemExit("라벨 파일이 없습니다. 먼저 `python main.py label <그룹>` 을 실행하세요.")
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["label"] in LABELS]
    counts = {lab: sum(r["label"] == lab for r in rows) for lab in LABELS}
    log.info("라벨 분포: %s", counts)
    if min(counts.values()) < 8:
        raise SystemExit(f"클래스마다 최소 8개 이상 필요합니다 (현재 {counts}).")

    random.Random(42).shuffle(rows)
    cut = int(len(rows) * 0.8)
    tr, te = rows[:cut], rows[cut:]
    to_ds = lambda rs: Dataset.from_dict({"text": [r["text"] for r in rs],
                                          "label": [LABELS.index(r["label"]) for r in rs]})

    base = settings["model"]["sbert"]
    model = SetFitModel.from_pretrained(base)
    args = TrainingArguments(batch_size=16, num_epochs=1, num_iterations=20)
    trainer = Trainer(model=model, args=args, train_dataset=to_ds(tr))
    trainer.train()

    y_true = [LABELS.index(r["label"]) for r in te]
    y_pred = list(np.asarray(model.predict([r["text"] for r in te])).astype(int))
    print("\n[SetFit] 검증 결과")
    print(classification_report(y_true, y_pred, target_names=list(LABELS), digits=3))

    # 앵커 방식과 비교
    from nlp.encoder import SbertEncoder
    enc = SbertEncoder(base, db=db)
    n = settings["nlp"]
    anchor = AnchorSentiment(enc, load_anchors(), n["anchor_topk"], n["temperature"])
    texts = [r["text"] for r in te]
    a_pred = anchor.predict(texts, enc.encode(texts)).argmax(axis=1)
    f_set = f1_score(y_true, y_pred, average="macro")
    f_anc = f1_score(y_true, a_pred, average="macro")
    print(f"macro-F1  SetFit {f_set:.3f}  vs  앵커 {f_anc:.3f}")

    out = ROOT / settings["model"]["setfit_path"]
    model.save_pretrained(str(out))
    (out / "label_map.json").write_text(json.dumps({"labels": list(LABELS), "base": base,
                                                    "macro_f1": f_set, "anchor_macro_f1": f_anc}))
    print(f"저장: {out}" + ("" if f_set > f_anc else "\n주의: 앵커보다 낮습니다. 라벨을 더 모으세요."))
