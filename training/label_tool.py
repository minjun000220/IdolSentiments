"""터미널 라벨링 도구. 학습 허용 출처(기본: 유튜브)의 문장만 무작위로 보여준다.

  1 = 부정   2 = 중립   3 = 긍정   s = 건너뛰기   q = 저장 후 종료
"""
import csv
import random
from pathlib import Path

from core.config import ROOT, GroupConfig
from preprocess.cleaner import clean, meaningful
from preprocess.splitter import split_sentences

KEYS = {"1": "neg", "2": "neu", "3": "pos"}


def run_labeling(group: GroupConfig, settings: dict, db, n: int) -> None:
    path = ROOT / settings["training"]["labels_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            done = {r["text"] for r in csv.DictReader(f)}

    docs = db.load_docs(group.key, sources=settings["training"]["trainable_sources"], trainable_only=True)
    pool = list({s for d in docs for s in split_sentences(clean(d.text))
                 if meaningful(s, 6) and s not in done})
    if not pool:
        print("라벨링할 문장이 없습니다. 먼저 수집하세요.")
        return
    random.shuffle(pool)
    counts = {"neg": 0, "neu": 0, "pos": 0}
    print(f"기존 라벨 {len(done)}개. 1=부정 2=중립 3=긍정 s=건너뛰기 q=종료\n"
          f"팁: 멤버/그룹에 대한 '평가'만 긍정/부정, 정보성 질문은 중립. 반어법은 실제 의미대로.\n")
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        if new:
            wr.writerow(["text", "label", "group"])
        for i, s in enumerate(pool[:n], 1):
            while True:
                k = input(f"[{i}/{min(n, len(pool))}] {s}\n  > ").strip().lower()
                if k in KEYS or k in ("s", "q"):
                    break
            if k == "q":
                break
            if k == "s":
                continue
            wr.writerow([s, KEYS[k], group.key])
            counts[KEYS[k]] += 1
    print(f"저장 완료: {path}  이번 세션 {counts}")
