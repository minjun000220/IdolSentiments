"""네트워크/모델 없이 전체 파이프라인을 검증하는 테스트.
실제 SBERT 대신 글자 n-gram 해시 인코더를 사용한다 (결과 수치는 의미 없음, 동작 확인용).

    python -m pytest tests -q
"""
import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.dcinside import parse_list, parse_view  # noqa: E402
from core.config import load_group, load_settings  # noqa: E402
from core.timeutil import now_utc, to_iso  # noqa: E402
from core.types import RawDoc  # noqa: E402
from preprocess.cleaner import clean  # noqa: E402
from preprocess.member_linker import GROUP, MemberLinker  # noqa: E402
from storage.db import DB  # noqa: E402


class HashEncoder:
    name = "hash-test"

    def encode(self, texts):
        out = np.zeros((len(texts), 256), dtype=np.float32)
        for i, t in enumerate(texts):
            for n in (1, 2):
                for j in range(len(t) - n + 1):
                    h = int(hashlib.md5(t[j:j + n].encode()).hexdigest(), 16)
                    out[i, h % 256] += 1
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


def test_cleaner():
    assert clean("ㅋㅋㅋㅋㅋ 민지 예쁘다!!!!!! https://x.com/a") == "ㅋㅋ 민지 예쁘다!!!"
    assert "dc official" not in clean("좋다\n- dc official App")


def test_linker_boundaries():
    g = load_group("뉴진스")
    lk = MemberLinker(g, load_settings()["scoring"]["conf"])
    assert lk.find_members("하니가 너무 귀엽다") == ["하니"]
    assert lk.find_members("너 뭐하니") == []          # 왼쪽 경계
    assert lk.find_members("하니까 좋네") == []          # exclude_patterns
    assert lk.find_members("Hanni and Minji") == ["민지", "하니"]
    links = lk.link_doc(["민지 오늘 대박", "진짜 예쁘다", "노래 좋다"], context_title="뉴진스 무대")
    assert [l[0].method for l in links] == ["explicit", "carry", "context_group"]
    links = lk.link_doc(["표정 미쳤다"], context_title="[직캠] 해린 HAERIN 4K")
    assert links[0][0].target == "해린" and links[0][0].method == "context_member"
    assert lk.link_doc(["뉴진스 컴백 좋다"], "")[0][0].target == GROUP


def test_dc_parsers():
    lst = """<table><tbody>
    <tr class="ub-content us-post" data-no="10" data-type="icon_notice"><td class="gall_num">10</td>
      <td class="gall_tit"><a>공지</a></td><td class="gall_date" title="2026-11-01 10:00:00">11.01</td></tr>
    <tr class="ub-content us-post" data-no="11" data-type="icon_txt"><td class="gall_num">11</td>
      <td class="gall_tit"><a href="#">민지 무대 좋다</a><a class="reply_numbox"><span class="reply_num">[5]</span></a></td>
      <td class="gall_date" title="2026-11-16 17:07:03">11.16</td><td class="gall_recommend">3</td></tr>
    </tbody></table>"""
    rows = parse_list(lst)
    assert len(rows) == 1 and rows[0]["no"] == "11" and rows[0]["replies"] == 5 and rows[0]["recommend"] == 3
    assert rows[0]["created_at"] == "2026-11-16T08:07:03"          # KST → UTC
    view = """<span class="title_subject">제목</span><span class="gall_date" title="2026-11-16 17:07:03"></span>
      <div class="write_div"><p>본문 내용</p><p>- dc official App</p></div>
      <input id="e_s_n_o" value="abc"><p class="up_num">4</p>"""
    v = parse_view(view)
    assert v["title"] == "제목" and v["body"] == "본문 내용" and v["esno"] == "abc" and v["recommend"] == 4


def _doc(i, src, text, title="", likes=0):
    return RawDoc(source=src, doc_id=str(i), kind="comment", text=text, group_key="newjeans",
                  context_title=title, likes=likes, created_at=to_iso(now_utc()), author_hash=f"a{i}")


def test_pipeline_end_to_end(tmp_path):
    import pipeline
    from nlp.sentiment import AnchorSentiment
    from core.config import load_anchors

    settings = load_settings()
    settings["scoring"]["bootstrap"] = 30
    db = DB(tmp_path / "t.db")
    texts = [
        ("youtube", "민지 진짜 너무 예쁘다 무대 찢었다", "뉴진스 무대", 50),
        ("youtube", "해린 표정 연기 대박 소름", "뉴진스 무대", 10),
        ("youtube", "하니 라이브 실력 대단하다", "", 5),
        ("dcinside", "다니엘 이번 무대 실망이다 별로", "", 0),
        ("dcinside", "혜인 컴백 언제예요", "", 0),
        ("youtube", "표정 미쳤다 사랑스럽다", "[직캠] 해린 4K", 3),
        ("youtube", "뉴진스 노래 너무 좋다 계속 듣는 중", "", 20),
        ("dcinside", "민지 태도가 별로다", "", 1),
    ] * 5
    db.upsert_docs([_doc(i, s, t, ti, lk) for i, (s, t, ti, lk) in enumerate(texts)])
    g = load_group("newjeans")
    enc = HashEncoder()
    sent = AnchorSentiment(enc, load_anchors(), 3, 0.05)
    r = pipeline.analyze(g, settings, db, days=30, encoder=enc, sentiment=sent, out_root=tmp_path)
    assert len(r["members"]) == 5
    for m in r["members"]:
        assert 0 <= m["favor"] <= 100 and 0 <= m["interest"] <= 100
        assert 1 <= m["rank_lo"] <= m["rank_hi"] <= 5
    assert 0 <= r["group"]["favor"] <= 100
    assert r["group"]["interest"] is not None and 0 <= r["group"]["interest"] <= 100
    assert abs(r["group"]["mentions_per_day"] - r["group"]["n"] / 30) < 1e-6
    top = max(r["members"], key=lambda m: m["n"])
    assert abs(top["interest"] - 100) < 1e-6                        # 언급 1위 멤버 = 관심도 100
    assert abs(sum(m["mention_share"] for m in r["members"]) - 1) < 1e-6
    assert set(r["by_source"]) == {"youtube", "dcinside"}
    assert (Path(r["out_dir"]) / "mentions.csv").exists()
    from report.console import print_report
    print_report(r)


# ---------------- 자동 설정 ----------------
def test_one_letter_member_boundary():
    from core.config import GroupConfig, Member
    g = GroupConfig(key="t", name="방탄소년단", aliases=["방탄소년단", "BTS"],
                    members=[Member("진", ["진", "Jin"]), Member("뷔", ["뷔", "태형"])])
    lk = MemberLinker(g, load_settings()["scoring"]["conf"])
    assert lk.find_members("진짜 좋다") == []
    assert lk.find_members("뷔페 가자") == []
    assert lk.find_members("진 노래 최고") == ["진"]
    assert lk.find_members("진이 부른 파트") == ["진"]
    assert lk.find_members("뷔가 너무 잘생겼다") == ["뷔"]


def test_member_name_rules():
    from discovery.wiki import make_member_from_names, parse_infobox_members
    assert make_member_from_names("강해린", "Haerin", ["해린"])["name"] == "해린"
    assert make_member_from_names("이로하", "Iroha", [])["name"] == "이로하"          # 성으로 착각해 줄이지 않음
    assert make_member_from_names("김남준", "RM", ["알엠"])["name"] == "RM"
    assert make_member_from_names("뷔 (가수)", "V", [])["aliases"] == ["뷔"]           # 영문 1글자 V 제외
    assert make_member_from_names("이로하", exact=True) == {"name": "이로하", "aliases": ["이로하"]}
    wt = "{{그룹 정보\n| 이름 = 테스트\n| 구성원 = [[김민지 (가수)|민지]], [[하니 (가수)|하니]]<br />다니엘\n| 레이블 = X\n}}"
    assert parse_infobox_members(wt) == ["민지", "하니", "다니엘"]


def test_dc_gallery_search_parser():
    from discovery.dc_galleries import parse_gallery_search, pick_galleries
    html = """<div class="integrate_cont gallsch_result_all"><ul class="integrate_cont_list">
    <li><a href="https://gall.dcinside.com/mgallery/board/lists/?id=newjeans" class="gallname_txt ">뉴진스<em class="icon_minor">ⓜ</em></a>
        <div class="integrate_gallinfo"><span class="info txtnum">새글 18/1,117,078</span></div></li>
    <li><a href="https://gall.dcinside.com/mgallery/board/lists/?id=kmjgall" class="gallname_txt ">뉴진스 민지<em>ⓜ</em></a>
        <div class="integrate_gallinfo"><span class="info txtnum">새글 10/260,863</span></div></li>
    <li><a href="https://gall.dcinside.com/mini/board/lists/?id=newjeans0722" class="gallname_txt ">뉴진스<em>ⓝ</em></a>
        <div class="integrate_gallinfo"><span class="info txtnum">새글 0/1,000</span></div></li>
    <li><a href="https://gall.dcinside.com/mgallery/board/lists/?id=ivewithnewjeans" class="gallname_txt ">아이브X뉴진스<em>ⓜ</em></a></li>
    <li><a href="https://gall.dcinside.com/person/board/lists/?id=hyein0421" class="gallname_txt ">이혜인</a></li>
    </ul></div>"""
    res = parse_gallery_search(html)
    assert [r["id"] for r in res] == ["newjeans", "kmjgall", "newjeans0722", "ivewithnewjeans"]
    assert res[0] == {"id": "newjeans", "type": "mgallery", "name": "뉴진스", "posts": 1117078}
    members = [{"name": "민지", "aliases": ["민지"]}]
    picked = pick_galleries(res, ["뉴진스", "NewJeans"], members, include_members=False, max_members=5)
    assert [p["id"] for p in picked] == ["newjeans"]                  # 글 수가 더 많은 쪽
    picked = pick_galleries(res, ["뉴진스"], members, include_members=True, max_members=5)
    assert picked[1]["id"] == "kmjgall" and picked[1]["member"] == "민지"


def test_web_export(tmp_path):
    import json
    from report.web_export import export_result
    g = load_group("newjeans")
    m = {"rank": 1, "name": "민지", "favor": 80.123, "interest": 90.0, "intensity": 70.0, "controversy": 0.1,
         "net": 0.8, "n": 40, "share": 0.5, "rank_lo": 1, "rank_hi": 2, "favor_lo": 70.0, "favor_hi": 85.0,
         "low_sample": False, "quadrant": "인기", "mention_share": 1.0, "examples": {"pos": ["좋다"], "neg": ["싫다 비난 문장"]}}
    result = {"computed_at": "2026-11-18T03:00:00", "days": 90, "sentiment_model": "anchor", "n_docs": 1,
              "n_sentences": 1, "n_mentions": 1, "group": {"favor": 70.0, "interest": None, "controversy": 0.1,
              "net": 0.8, "energy": 3.0, "n": 1.0, "n_direct": 0.0, "favor_direct": None, "favor_members": 70.0},
              "members": [m], "by_source": {"youtube": {"n": 1, "pos_ratio": 0.9, "net": 0.8, "controversy": 0.1}}}
    export_result(result, g, tmp_path)
    export_result(result | {"computed_at": "2026-11-19T03:00:00"}, g, tmp_path)
    page = json.loads((tmp_path / "groups" / "newjeans.json").read_text(encoding="utf-8"))
    assert page["members"][0]["examples"] == ["좋다"]                  # 부정 예시는 공개하지 않음
    assert "싫다" not in json.dumps(page, ensure_ascii=False)
    assert [h["date"] for h in page["history"]] == ["2026-11-18", "2026-11-19"]
    idx = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(idx["groups"]) == 1 and idx["groups"][0]["top_member"] == "민지"


def test_group_interest_absolute():
    from scoring.metrics import group_interest
    gi, per_day = group_interest(30262, 90, 5000)                  # 아일릿 실제 값
    assert abs(per_day - 336.2) < 0.1 and abs(gi - 68.3) < 0.1
    assert group_interest(1e9, 90, 5000)[0] == 100.0               # 상한


def test_youtube_search_skips_non_video_items(tmp_path):
    from datetime import timedelta
    from collectors.youtube import YouTubeCollector
    yt = YouTubeCollector(load_settings(), DB(tmp_path / "y.db"), "dummy")
    yt.cfg["max_searches"] = 1
    items = [{"id": {"kind": "youtube#channel", "channelId": "UC1"}, "snippet": {"title": "채널"}},
             {"id": {"kind": "youtube#video", "videoId": "v1"}, "snippet": {"title": "영상", "publishedAt": ""}},
             {"id": {"kind": "youtube#playlist"}}]
    yt._call = lambda endpoint, **kw: {"items": items}
    vids = yt.find_videos(load_group("newjeans"), now_utc() - timedelta(days=30))
    assert list(vids) == ["v1"]


def test_common_word_aliases_filtered():
    from discovery.wiki import make_member_from_names
    m = make_member_from_names("리즈", "Liz", ["김지원", "Kim Ji-won"])
    assert "지원" not in m["aliases"] and "김지원" in m["aliases"]
    assert make_member_from_names("가을", "Gaeul", ["김가을"])["name"] == "가을"   # 대표 이름은 유지
