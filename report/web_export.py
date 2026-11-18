"""분석 결과 → 웹(web/public/data)용 JSON.

공개 페이지에 올라가므로:
  - 부정 예시 문장은 넣지 않음 (특정 멤버를 공격하는 인용으로 쓰일 수 있음)
  - 긍정 예시 문장도 원문 링크/작성자 정보 없이 짧게만
"""
import json
from pathlib import Path

from core.config import ROOT, GroupConfig

WEB_DATA = ROOT / "web" / "public" / "data"
HISTORY_LIMIT = 90

MEMBER_KEYS = ("rank", "name", "favor", "interest", "intensity", "controversy", "net", "n", "share",
               "rank_lo", "rank_hi", "favor_lo", "favor_hi", "low_sample", "quadrant", "mention_share")


def _r(v, nd=2):
    return round(v, nd) if isinstance(v, float) else v


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def export_result(result: dict, group: GroupConfig, out_dir: Path = WEB_DATA) -> Path:
    members = []
    for m in result["members"]:
        d = {k: _r(m[k]) for k in MEMBER_KEYS}
        d["examples"] = [x[:60] for x in m["examples"]["pos"][:2]]
        members.append(d)
    g = {k: _r(v) for k, v in result["group"].items()}
    page = {
        "key": group.key,
        "name": group.name,
        "aliases": group.aliases,
        "updated_at": result["computed_at"] + "Z",
        "days": result["days"],
        "sentiment_model": result["sentiment_model"],
        "counts": {"docs": result["n_docs"], "sentences": result["n_sentences"], "mentions": result["n_mentions"]},
        "group": g,
        "members": members,
        "by_source": {k: {kk: _r(vv) for kk, vv in v.items()} for k, v in result["by_source"].items()},
    }

    # 추이: 실행할 때마다 한 줄씩 (같은 날짜는 덮어씀)
    hist_path = out_dir / "groups" / f"{group.key}.history.json"
    hist = [h for h in _load(hist_path, []) if h["date"] != page["updated_at"][:10]]
    hist.append({"date": page["updated_at"][:10], "favor": g["favor"], "interest": g.get("interest"),
                 "mentions_per_day": g.get("mentions_per_day"),
                 "members": {m["name"]: m["favor"] for m in members}})
    hist = sorted(hist, key=lambda h: h["date"])[-HISTORY_LIMIT:]
    page["history"] = hist
    _write(hist_path, hist)
    _write(out_dir / "groups" / f"{group.key}.json", page)

    # 목록
    idx_path = out_dir / "index.json"
    idx = [x for x in _load(idx_path, {"groups": []})["groups"] if x["key"] != group.key]
    top = members[0]["name"] if members else None
    idx.append({"key": group.key, "name": group.name, "aliases": group.aliases, "updated_at": page["updated_at"],
                "favor": g["favor"], "interest": g.get("interest"),
                "members": [m["name"] for m in members],
                "top_member": top, "mentions": result["n_mentions"]})
    idx.sort(key=lambda x: x["name"])
    _write(idx_path, {"groups": idx})
    return out_dir / "groups" / f"{group.key}.json"
