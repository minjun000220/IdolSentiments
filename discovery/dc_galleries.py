"""디시 갤러리 검색 → 그룹 전용 갤러리 / 멤버 갤러리 찾기.

검색 결과 예: "뉴진스ⓜ"(그룹), "뉴진스 민지ⓜ"(멤버), "아이브X뉴진스ⓜ"(무관) ...
"""
import re
from urllib.parse import parse_qs, quote, urlparse

from bs4 import BeautifulSoup

SEARCH = "https://search.dcinside.com/gallery/q/"
TYPE_BY_PATH = {"mgallery": "mgallery", "mini": "mini", "board": "main"}


def _norm(s: str) -> str:
    return re.sub(r"[\sⓜⓝ\-_()]", "", s).lower()


def parse_gallery_search(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.select(".gallsch_result_all a.gallname_txt, .integrate_cont_list a.gallname_txt"):
        href = a.get("href", "")
        u = urlparse(href)
        gid = (parse_qs(u.query).get("id") or [""])[0]
        first = u.path.strip("/").split("/")[0]
        gtype = TYPE_BY_PATH.get(first)
        if not gid or not gtype or gid in seen:      # 인물갤(person) 등은 제외
            continue
        seen.add(gid)
        for em in a.select("em"):
            em.decompose()
        info = a.find_next("span", class_="txtnum")
        total = 0
        if info:
            nums = re.findall(r"[\d,]+", info.get_text())
            total = int(nums[-1].replace(",", "")) if nums else 0
        out.append({"id": gid, "type": gtype, "name": a.get_text(strip=True), "posts": total})
    return out


def search_galleries(http, keyword: str) -> list[dict]:
    r = http.get(SEARCH + quote(keyword))
    return parse_gallery_search(r.text) if r.status_code == 200 else []


def pick_galleries(results: list[dict], group_names: list[str], members: list[dict],
                   include_members: bool, max_members: int) -> list[dict]:
    """이름이 그룹명과 정확히 같은 갤러리 = 그룹 갤러리 (게시글 수 가장 많은 것 1개).
    '그룹명 멤버명' 형태 = 멤버 갤러리."""
    gnorms = {_norm(n) for n in group_names if n}
    main = [g for g in results if _norm(g["name"]) in gnorms]
    main.sort(key=lambda g: -g["posts"])
    picked = [{"id": main[0]["id"], "type": main[0]["type"], "mode": "list", "name": main[0]["name"]}] if main else []

    if include_members:
        for m in members:
            keys = {gn + _norm(a) for gn in gnorms for a in m["aliases"]}
            cands = sorted([g for g in results if _norm(g["name"]) in keys], key=lambda g: -g["posts"])
            if cands:
                c = cands[0]
                picked.append({"id": c["id"], "type": c["type"], "mode": "list", "name": c["name"],
                               "member": m["name"]})
            if len(picked) - 1 >= max_members:
                break
    return picked
