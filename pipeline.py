import csv
import json
import logging
import os
from datetime import timedelta
from pathlib import Path

import numpy as np

from core.config import ROOT, GroupConfig, load_anchors
from core.timeutil import age_days, now_utc, to_iso
from preprocess.cleaner import clean, meaningful
from preprocess.dedup import near_duplicate_mask
from preprocess.member_linker import GROUP, MemberLinker
from preprocess.splitter import split_sentences
from scoring.metrics import aggregate, compute_scores, group_interest, quadrant
from scoring.ranking import bootstrap_ranks
from scoring.weights import mention_weights
from storage.db import DB

log = logging.getLogger(__name__)
SOURCES = ("youtube", "dcinside")
CONTEXT_METHODS = {"context_member", "context_group"}


# ============================================================ 수집
def collect(group: GroupConfig, settings: dict, db: DB, sources=SOURCES, days: int | None = None) -> dict:
    since = now_utc() - timedelta(days=days or settings["collect"]["days"])
    counts = {}
    if "youtube" in sources:
        try:
            from collectors.youtube import YouTubeCollector
            yt = YouTubeCollector(settings, db, os.environ.get("YOUTUBE_API_KEY", ""))
            counts["youtube"] = len(yt.collect(group, since))
        except Exception:
            # 이미 수집한 영상의 댓글은 영상 단위로 DB에 저장돼 있으므로 그대로 분석에 쓰임
            log.exception("[YouTube] 수집 중 오류 → 유튜브는 여기까지만 사용하고 계속 진행")
            counts["youtube"] = "error"
    if "dcinside" in sources:
        try:
            from collectors.dcinside import DCInsideCollector
            counts["dcinside"] = len(DCInsideCollector(settings).collect(group, since, db=db))
        except Exception:
            log.exception("[DC] 수집 중 오류 → 계속 진행")
            counts["dcinside"] = "error"
    return counts


# ============================================================ 분석
def build_mentions(docs, linker: MemberLinker, pp: dict):
    """원문 → 문장 → 멤버 연결. 같은 작성자의 같은 글(도배)은 하나만 남김."""
    seen = set()
    sents, mentions = [], []
    for d in docs:
        key = (d.author_hash, d.text.strip())
        if d.author_hash and key in seen:
            continue
        seen.add(key)
        parts = [s for s in split_sentences(clean(d.text), pp["max_chars"]) if meaningful(s, pp["min_chars"])]
        for s, links in zip(parts, linker.link_doc(parts, d.context_title)):
            sid = len(sents)
            sents.append({"text": s, "source": d.source, "likes": d.likes, "created_at": d.created_at,
                          "url": d.url, "doc_uid": d.uid})
            for lk in links:
                mentions.append({"sid": sid, "target": lk.target, "conf": lk.conf, "method": lk.method})
    return sents, mentions


def analyze(group: GroupConfig, settings: dict, db: DB, days: int | None = None,
            encoder=None, sentiment=None, out_root: Path | None = None, plot: bool = False) -> dict:
    days = days or settings["collect"]["days"]
    since = to_iso(now_utc() - timedelta(days=days))
    docs = db.load_docs(group.key, since)
    if not docs:
        raise SystemExit(f"'{group.name}' 수집 데이터가 없습니다. 먼저 collect 를 실행하세요.")
    log.info("원문 %d건 로드", len(docs))

    anchors = load_anchors()
    if encoder is None:
        from nlp.encoder import SbertEncoder
        m = settings["model"]
        encoder = SbertEncoder(m["sbert"], db=db, device=m["device"], batch_size=m["batch_size"])
    if sentiment is None:
        from nlp.sentiment import build_sentiment
        sentiment = build_sentiment(settings, encoder, anchors, ROOT)
    from nlp.relevance import RelevanceScorer
    rel_scorer = RelevanceScorer(encoder, anchors["relevance"], settings["nlp"]["relevance_low"],
                                 settings["nlp"]["relevance_high"])

    # 1) 문장 + 멤버 연결
    linker = MemberLinker(group, settings["scoring"]["conf"])
    sents, mentions = build_mentions(docs, linker, settings["preprocess"])
    log.info("문장 %d개, 연결 %d개", len(sents), len(mentions))

    # 2) 임베딩 + 도배 제거
    texts = [s["text"] for s in sents]
    emb = encoder.encode(texts)
    keep = near_duplicate_mask(emb, np.array([len(t) for t in texts]), settings["preprocess"]["near_dup_threshold"])
    log.info("유사 중복 제거: %d개", int((~keep).sum()))

    # 3) 감성 + 관련성
    probs = sentiment.predict(texts, emb)                 # (n, 3) = neg, neu, pos
    rel = rel_scorer.score(emb)

    # 4) 언급 단위 배열
    targets = group.member_names + [GROUP]
    tix = {n: i for i, n in enumerate(targets)}
    mentions = [m for m in mentions if keep[m["sid"]]]
    sid = np.array([m["sid"] for m in mentions], dtype=int)
    t = np.array([tix[m["target"]] for m in mentions], dtype=int)
    conf = np.array([m["conf"] for m in mentions])
    is_ctx = np.array([m["method"] in CONTEXT_METHODS for m in mentions])
    relevance = np.where(is_ctx, rel[sid], 1.0)
    source = np.array([sents[i]["source"] for i in sid])
    likes = np.array([sents[i]["likes"] for i in sid], dtype=float)
    ref = now_utc()
    ages = np.array([age_days(sents[i]["created_at"], ref) for i in sid])
    sc = settings["scoring"]
    w = mention_weights(source, likes, ages, conf, relevance, sc)
    pneg, pneu, ppos = probs[sid, 0], probs[sid, 1], probs[sid, 2]

    valid = w > 1e-6
    sid, t, w, ppos, pneg, pneu, source, conf, relevance = (
        a[valid] for a in (sid, t, w, ppos, pneg, pneu, source, conf, relevance))
    methods = [m["method"] for m, v in zip(mentions, valid) if v]

    # 5) 점수
    M = len(group.members)
    scores = compute_scores(aggregate(t, w, ppos, pneg, M + 1), M, sc)
    boot = bootstrap_ranks(t, w, ppos, pneg, M, sc)
    scores["group"]["interest"], scores["group"]["mentions_per_day"] = group_interest(
        scores["group"]["n"], days, sc["interest_ref_per_day"])

    mem = scores["members"]
    f_mid, i_mid = float(np.median(mem["favor"])), float(np.median(mem["interest"]))
    order = np.argsort(-mem["favor"])
    members = []
    for rank, i in enumerate(order, 1):
        members.append({
            "rank": rank, "name": targets[i],
            "favor": float(mem["favor"][i]), "interest": float(mem["interest"][i]),
            "intensity": float(mem["intensity"][i]), "controversy": float(mem["controversy"][i]),
            "net": float(mem["net"][i]), "n": int(mem["n"][i]), "share": float(mem["share"][i]),
            "mention_share": float(mem["n"][i] / max(mem["n"].sum(), 1)),
            "rank_lo": int(boot["rank_lo"][i]), "rank_hi": int(boot["rank_hi"][i]),
            "favor_lo": float(boot["favor_lo"][i]), "favor_hi": float(boot["favor_hi"][i]),
            "low_sample": bool(mem["n"][i] < sc["min_mentions"]),
            "quadrant": quadrant(mem["favor"][i], mem["interest"][i], f_mid, i_mid, mem["controversy"][i]),
            "examples": _examples(i, t, w, ppos, pneg, sid, sents),
        })

    by_source = {}
    for s in sorted(set(source)):
        mk = source == s
        P, N_, W_ = (w[mk] * ppos[mk]).sum(), (w[mk] * pneg[mk]).sum(), w[mk].sum()
        by_source[s] = {"n": int(mk.sum()), "pos_ratio": float(P / max(W_, 1e-9)),
                        "net": float((P - N_) / max(P + N_, 1e-9)), "controversy": float(N_ / max(P + N_, 1e-9))}

    result = {
        "group_key": group.key, "group_name": group.name, "days": days,
        "computed_at": to_iso(ref), "sentiment_model": getattr(sentiment, "name", "?"),
        "n_docs": len(docs), "n_sentences": len(sents), "n_mentions": int(len(t)),
        "group": scores["group"], "members": members, "by_source": by_source,
    }
    db.save_snapshot(group.key, result["computed_at"], days,
                     {k: v for k, v in result.items() if k != "members"} | {
                         "members": [{k: v for k, v in m.items() if k != "examples"} for m in members]})

    out_dir = _write_outputs(result, sents, sid, t, w, ppos, pneg, pneu, conf, relevance, methods, targets,
                             out_root or ROOT / "outputs")
    result["out_dir"] = str(out_dir)
    if plot:
        from report.charts import quadrant_chart
        result["chart"] = str(quadrant_chart(result, out_dir / "quadrant.png"))
    return result


def _examples(i, t, w, ppos, pneg, sid, sents, n=2):
    """대표 문장: 해당 감성이 가장 높은 확률인 문장 중 가중치×확률 상위, 중복 제거."""
    mk = np.where(t == i)[0]
    out = {"pos": [], "neg": []}
    for key, p, other in (("pos", ppos, pneg), ("neg", pneg, ppos)):
        cand = mk[(p[mk] > other[mk]) & (p[mk] >= 0.4)]
        for j in cand[np.argsort(-(w * p)[cand])]:
            txt = sents[sid[j]]["text"][:80]
            if txt not in out[key]:
                out[key].append(txt)
            if len(out[key]) >= n:
                break
    return out


def _write_outputs(result, sents, sid, t, w, ppos, pneg, pneu, conf, rel, methods, targets, out_root: Path) -> Path:
    stamp = result["computed_at"].replace(":", "").replace("-", "")[:13]
    out = out_root / f"{result['group_key']}_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "scores.csv", "w", newline="", encoding="utf-8-sig") as f:
        cols = ["rank", "name", "favor", "interest", "controversy", "net", "intensity", "n", "share",
                "rank_lo", "rank_hi", "quadrant", "low_sample"]
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        for m in result["members"]:
            wr.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()})
    # 문장 단위 결과: 감성 분석이 맞는지 직접 눈으로 확인하는 용도
    with open(out / "mentions.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["target", "method", "source", "p_pos", "p_neg", "p_neu", "weight", "conf", "relevance",
                     "created_at", "text", "url"])
        for j in np.argsort(-w):
            s = sents[sid[j]]
            wr.writerow([targets[t[j]], methods[j], s["source"], f"{ppos[j]:.3f}", f"{pneg[j]:.3f}",
                         f"{pneu[j]:.3f}", f"{w[j]:.3f}", f"{conf[j]:.2f}", f"{rel[j]:.2f}", s["created_at"],
                         s["text"], s["url"]])
    return out
