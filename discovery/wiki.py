"""그룹 이름 → 멤버 목록 (위키데이터 우선, 실패 시 한국어 위키백과 인포박스).

위키데이터:
  1. wbsearchentities 로 후보 검색
  2. wbgetentities 로 후보들의 설명/분류/구성원(P527) 확인 → 음악 그룹 후보 선택
  3. P527(has part) 중 종료일(P582)이 없는 항목 = 현재 멤버, 각 멤버의 한/영 이름과 별칭 수집
"""
import logging
import re
import time

import requests

log = logging.getLogger(__name__)

WIKIDATA = "https://www.wikidata.org/w/api.php"
KOWIKI = "https://ko.wikipedia.org/w/api.php"

# 음악 그룹 계열 분류 (instance of, P31)
GROUP_TYPES = {"Q215380", "Q2088357", "Q216337", "Q641066", "Q9212979", "Q5741069"}
GROUP_WORDS = ("그룹", "걸그룹", "보이그룹", "밴드", "group", "band", "girl group", "boy band", "idol")
SURNAMES = set("김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진나지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예봉경사부")
PAREN_RE = re.compile(r"\s*[\(（].*?[\)）]")
# 이름이지만 일반 단어로 훨씬 자주 쓰이는 것들. 본명/별칭에서 자동으로 만든 별칭이면 제외
# (멤버의 대표 이름 자체가 이 단어면 그대로 두되 경고만 표시)
COMMON_WORDS = set("""지원 가을 여름 겨울 하늘 보라 나라 소원 사랑 은하 미소 이슬 노을 바다 다솜 수정 정원 민주
지수 진주 하나 태양 한결 우주 누리 보람 성공 소망 희망 기쁨 현재 미래 소라 나무 구름 보미 세상""".split())


class Wiki:
    def __init__(self, user_agent: str, delay: float = 1.0):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = user_agent
        self.delay = delay
        self._last = 0.0

    def _get(self, url: str, retries: int = 3, **params) -> dict:
        for attempt in range(retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            r = self.s.get(url, params={**params, "format": "json"}, timeout=20)
            if r.status_code != 429:
                r.raise_for_status()
                return r.json()
            if attempt < retries:
                ra = r.headers.get("Retry-After", "")
                backoff = min(int(ra), 60) if ra.isdigit() else 5 * 2 ** attempt
                log.info("위키미디어 요청 제한(429) → %ds 후 재시도", backoff)
                time.sleep(backoff)
        raise RuntimeError("위키미디어 요청 제한(429)이 계속됩니다. 잠시 후 다시 시도하거나 settings.yaml 의 "
                           "discovery.wiki_user_agent 에 연락처를 넣어주세요.")

    # ---------------- 위키데이터 ----------------
    def search_group(self, query: str) -> dict | None:
        ids = []
        for lang in ("ko", "en"):
            res = self._get(WIKIDATA, action="wbsearchentities", search=query, language=lang, uselang=lang,
                            type="item", limit=10)
            ids += [x["id"] for x in res.get("search", []) if x["id"] not in ids]
            if ids:
                break
        if not ids:
            return None
        ents = self._entities(ids)
        scored = []
        for rank, qid in enumerate(ids):
            e = ents.get(qid)
            if not e:
                continue
            claims = e.get("claims", {})
            types = {_claim_id(c) for c in claims.get("P31", [])}
            desc = " ".join(_text(e, "descriptions", l) for l in ("ko", "en")).lower()
            score = (3 if types & GROUP_TYPES else 0) + (2 if any(w in desc for w in GROUP_WORDS) else 0) \
                + (2 if claims.get("P527") else 0) + (1 if _norm(query) in {_norm(n) for n in _names(e)} else 0) \
                - rank * 0.1
            scored.append((score, qid, e))
        scored.sort(key=lambda x: -x[0])
        if not scored or scored[0][0] < 3:
            return None
        return {"qid": scored[0][1], "entity": scored[0][2]}

    def _entities(self, ids: list[str]) -> dict:
        out = {}
        for i in range(0, len(ids), 50):
            res = self._get(WIKIDATA, action="wbgetentities", ids="|".join(ids[i:i + 50]),
                            props="labels|aliases|descriptions|claims", languages="ko|en")
            out.update(res.get("entities", {}))
        return out

    def group_info(self, query: str) -> dict | None:
        """→ {"name_ko", "name_en", "aliases", "members": [{"name", "aliases"}], "source"}"""
        found = self.search_group(query)
        if not found:
            return None
        e = found["entity"]
        member_ids = []
        for c in e.get("claims", {}).get("P527", []):
            if c.get("rank") == "deprecated" or "P582" in c.get("qualifiers", {}):
                continue  # 탈퇴 멤버 제외
            mid = _claim_id(c)
            if mid:
                member_ids.append(mid)
        ments = self._entities(member_ids) if member_ids else {}
        members = [m for m in (make_member(ments[mid]) for mid in member_ids if mid in ments) if m]
        return {
            "name_ko": PAREN_RE.sub("", _text(e, "labels", "ko")).strip(),
            "name_en": PAREN_RE.sub("", _text(e, "labels", "en")).strip(),
            "aliases": [PAREN_RE.sub("", a).strip() for a in _aliases(e)],
            "members": members,
            "source": f"wikidata:{found['qid']}",
        }

    # ---------------- 위키백과 (대체) ----------------
    def group_info_kowiki(self, query: str) -> dict | None:
        res = self._get(KOWIKI, action="parse", page=query, prop="wikitext", redirects=1, formatversion=2)
        wt = (res.get("parse") or {}).get("wikitext", "")
        if not wt:
            return None
        names = parse_infobox_members(wt)
        if not names:
            return None
        title = res["parse"].get("title", query)
        return {
            "name_ko": PAREN_RE.sub("", title).strip(), "name_en": "", "aliases": [],
            "members": [m for m in (make_member_from_names(n) for n in names) if m],
            "source": f"kowiki:{title}",
        }


# ---------------- 헬퍼 ----------------
def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _text(e: dict, field: str, lang: str) -> str:
    return ((e.get(field) or {}).get(lang) or {}).get("value", "")


def _aliases(e: dict) -> list[str]:
    return [a["value"] for lang in ("ko", "en") for a in (e.get("aliases") or {}).get(lang, [])]


def _names(e: dict) -> list[str]:
    return [n for n in (_text(e, "labels", "ko"), _text(e, "labels", "en"), *_aliases(e)) if n]


def _claim_id(c: dict) -> str:
    try:
        return c["mainsnak"]["datavalue"]["value"]["id"]
    except (KeyError, TypeError):
        return ""


def _clean_alias(a: str) -> str:
    """한글은 1글자도 허용("뷔", "진"), 영문은 2글자 이상("V" 같은 1글자는 오탐이 너무 많음)."""
    a = PAREN_RE.sub("", a).strip()
    if not re.fullmatch(r"[가-힣A-Za-z0-9 .\-']+", a) or len(a) > 20:
        return ""
    return a if len(a) >= 2 or re.fullmatch(r"[가-힣]", a) else ""


def _given(a: str) -> str:
    """'강해린' → '해린' (성+이름 3글자로 보이면 이름 2글자)."""
    return a[1:] if re.fullmatch(r"[가-힣]{3}", a) and a[0] in SURNAMES else ""


def make_member_from_names(ko: str, en: str = "", aliases: list[str] | None = None,
                           exact: bool = False) -> dict | None:
    """exact=True(사용자가 직접 입력)면 이름을 그대로 쓴다."""
    ko, en = _clean_alias(ko), _clean_alias(en)
    display = ko or en
    if not display:
        return None
    if exact:
        return {"name": display, "aliases": [display]}
    others = [x for x in (_clean_alias(a) for a in [en, *(aliases or [])]) if x]
    # 표시명은 '이름 2글자'가 별칭에도 있을 때만 줄임 ("이로하"를 "로하"로 잘못 줄이지 않도록)
    g = _given(display)
    if g and g in others:
        display = g                       # "강해린" + 별칭 "해린" → 해린
    elif g and en and en.replace(".", "").isupper():
        display = en                      # "김남준" + 영문 "RM" → RM (대문자 예명)
    al = [display]
    for a in [ko, *others]:
        for x in (a, _given(a)):
            if x and len(x) >= 2 and x not in al and x not in COMMON_WORDS:
                al.append(x)
    return {"name": display, "aliases": al}


def make_member(e: dict) -> dict | None:
    return make_member_from_names(_text(e, "labels", "ko"), _text(e, "labels", "en"), _aliases(e))


INFOBOX_KEYS = r"(?:현재\s*구성원|구성원|현\s*멤버|멤버|current_members|members)"


def parse_infobox_members(wikitext: str) -> list[str]:
    m = re.search(rf"\|\s*{INFOBOX_KEYS}\s*=\s*(.*?)(?=\n\s*\||\n\}}\}})", wikitext, re.S)
    if not m:
        return []
    v = m.group(1)
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", v)        # [[대상|표시]] → 표시
    v = re.sub(r"\{\{\s*·\s*\}\}|\{\{\s*[Pp]lainlist\s*\||\{\{\s*[Uu]bl\s*\|", ",", v)
    v = re.sub(r"<br\s*/?>|\n\s*\*|\|", ",", v)
    v = re.sub(r"\{\{|\}\}|<[^>]+>|'''?", "", v)
    names = [PAREN_RE.sub("", x).strip(" *") for x in re.split(r"[,、·\n]", v)]
    return [n for n in names if n and len(n) <= 20]
