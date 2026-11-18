"""그룹 이름 하나로 config/groups/<키>.yaml 을 자동 생성.

  1. 위키데이터 → (실패 시) 한국어 위키백과 에서 그룹 정식명, 별칭, 현재 멤버
  2. 디시 갤러리 검색으로 그룹 갤러리 (+ 선택: 멤버 갤러리)
  3. 결과를 보여주고 확인 → 저장
"""
import hashlib
import logging
import re

import yaml

from collectors.base import PoliteSession
from core.config import CONFIG_DIR, GroupConfig, load_group
from discovery.dc_galleries import pick_galleries, search_galleries
from discovery.wiki import Wiki, make_member_from_names

log = logging.getLogger(__name__)


def _key(name_en: str, query: str) -> str:
    for s in (name_en, query):
        k = re.sub(r"[^a-z0-9가-힣]+", "", (s or "").lower())
        if k:
            return k
    return "g" + hashlib.sha1(query.encode()).hexdigest()[:8]


def _auto_excludes(alias: str) -> list[str]:
    # "하니", "다니" 처럼 '니'로 끝나는 2글자 한글 이름은 "~하니까" 같은 어미와 겹침
    if re.fullmatch(r"[가-힣]니", alias):
        return [f"{alias}까", f"{alias}깐", f"{alias}\\s*\\?"]
    return []


def _fetch_wiki(query: str, ua: str) -> dict | None:
    wiki = Wiki(ua)
    for fn, label in ((wiki.group_info, "위키데이터"), (wiki.group_info_kowiki, "위키백과")):
        try:
            info = fn(query)
        except Exception as e:
            log.warning("%s 조회 실패: %s", label, e)
            continue
        if info and info["members"]:
            log.info("%s에서 '%s' 멤버 %d명 찾음", label, info["name_ko"] or info["name_en"], len(info["members"]))
            return info
    return None


def _print_summary(name, aliases, members, galleries, source):
    print(f"\n[자동 설정] {name}   (출처: {source})")
    print(f"  그룹 별칭: {', '.join(aliases)}")
    print(f"  멤버 {len(members)}명:")
    for m in members:
        print(f"    - {m['name']:8s} 별칭: {', '.join(m['aliases'])}")
    print("  디시 갤러리:")
    for g in galleries:
        tag = f" (멤버: {g['member']})" if g.get("member") else ""
        print(f"    - {g.get('name', g['id'])} [{g['type']}/{g['id']}] {g['mode']}{tag}")
    short = [a for m in members for a in m["aliases"] if re.fullmatch(r"[가-힣]{1,2}", a)]
    if short:
        print(f"  참고: 1~2글자 이름({', '.join(short)})은 일반 단어와 겹칠 수 있습니다. "
              f"오탐이 보이면 yaml의 exclude_patterns 에 추가하세요.")


def auto_setup(query: str, settings: dict, members_override: list[str] | None = None,
               assume_yes: bool = False) -> GroupConfig:
    d = settings["discovery"]
    if "CHANGE-ME" in d["wiki_user_agent"]:
        log.warning("settings.yaml 의 discovery.wiki_user_agent 에 연락처를 넣어주세요 (위키미디어 정책)")

    info = None if members_override else _fetch_wiki(query, d["wiki_user_agent"])
    if members_override:
        members = [m for m in (make_member_from_names(n.strip(), exact=True) for n in members_override) if m]
        name_ko, name_en, aliases, source = query, "", [], "직접 입력"
    elif info:
        members = info["members"]
        name_ko, name_en, aliases, source = info["name_ko"] or query, info["name_en"], info["aliases"], info["source"]
    else:
        if assume_yes:
            raise SystemExit(f"'{query}' 멤버를 자동으로 찾지 못했습니다. --members 민지,하니,... 로 직접 지정하세요.")
        print(f"'{query}' 멤버를 자동으로 찾지 못했습니다.")
        typed = input("멤버 이름을 쉼표로 입력하세요 (예: 민지,하니,다니엘): ").strip()
        if not typed:
            raise SystemExit("취소했습니다.")
        members = [m for m in (make_member_from_names(n.strip(), exact=True) for n in typed.split(",")) if m]
        name_ko, name_en, aliases, source = query, "", [], "직접 입력"

    group_aliases = list(dict.fromkeys(a for a in [name_ko, query, name_en, *aliases] if a and len(a) >= 2))

    # 디시 갤러리
    c = settings["collect"]
    http = PoliteSession(c["user_agent"], c["request_delay_sec"])
    galleries = []
    for kw in dict.fromkeys([name_ko, name_en, query]):
        if not kw:
            continue
        try:
            results = search_galleries(http, kw)
        except Exception as e:
            log.warning("디시 갤러리 검색 실패 (%s): %s", kw, e)
            continue
        galleries = pick_galleries(results, group_aliases, members, d["include_member_galleries"],
                                   d["max_member_galleries"])
        if galleries:
            break
    if not galleries:
        log.warning("그룹 전용 디시 갤러리를 못 찾아서 일반 갤러리 검색 모드를 사용합니다.")
        galleries = [dict(g) for g in d["fallback_galleries"]]

    while True:
        _print_summary(name_ko, group_aliases, members, galleries, source)
        if assume_yes:
            break
        ans = input("\nEnter=저장 / 멤버 수정은 쉼표로 다시 입력 / n=취소 > ").strip()
        if ans.lower() == "n":
            raise SystemExit("취소했습니다.")
        if not ans:
            break
        members = [m for m in (make_member_from_names(n.strip(), exact=True) for n in ans.split(",")) if m]

    key = _key(name_en, query)
    doc = {
        "group": {"name": name_ko, "aliases": group_aliases},
        "members": {m["name"]: {"aliases": m["aliases"],
                                **({"exclude_patterns": ex} if (ex := [p for a in m["aliases"] for p in _auto_excludes(a)]) else {})}
                    for m in members},
        "youtube": {"queries": [], "channel_ids": []},
        "dcinside": {"galleries": galleries},
    }
    path = CONFIG_DIR / "groups" / f"{key}.yaml"
    header = (f"# 자동 생성됨 (출처: {source}). 멤버/별칭/갤러리가 틀리면 직접 고쳐도 됩니다.\n"
              f"# 다시 만들려면: python main.py setup \"{query}\" --refresh\n")
    path.write_text(header + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"저장: {path}")
    return load_group(key)
