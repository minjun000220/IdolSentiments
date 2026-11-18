"""디시인사이드 갤러리 수집기.

- 목록 페이지: 제목/날짜/추천/댓글수 (확인된 구조: tr.ub-content.us-post)
- 댓글이 많은 글만 본문 + 댓글까지 수집, 나머지는 제목만 (요청 수 절약)
- robots.txt 에서 금지된 갤러리는 자동으로 건너뜀
"""
import html as htmllib
import logging
import re
from datetime import datetime
from urllib.parse import quote

from bs4 import BeautifulSoup

from collectors.base import PoliteSession, RobotsDisallowed, hash_author
from core.config import GroupConfig
from core.timeutil import kst_to_iso, parse_iso
from core.types import RawDoc

log = logging.getLogger(__name__)

BASE = "https://gall.dcinside.com"
PATH = {"main": "/board", "mgallery": "/mgallery/board", "mini": "/mini/board"}
GALLTYPE = {"main": "G", "mgallery": "M", "mini": "MI"}
SIG_RE = re.compile(r"-\s*dc official App|- dc App", re.I)


def list_url(gal: dict, page: int, keyword: str | None = None) -> str:
    u = f"{BASE}{PATH[gal['type']]}/lists/?id={gal['id']}&page={page}"
    if keyword:
        u += f"&s_type=search_subject_memo&s_keyword={quote(keyword)}"
    return u


def view_url(gal: dict, no: str) -> str:
    return f"{BASE}{PATH[gal['type']]}/view/?id={gal['id']}&no={no}"


def parse_list(html: str) -> list[dict]:
    """갤러리 목록 HTML → 게시글 정보 리스트 (공지/광고/설문 제외)."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tr.ub-content.us-post"):
        no = tr.get("data-no", "")
        dtype = tr.get("data-type", "")
        num_td = tr.select_one("td.gall_num")
        if not no.isdigit() or "notice" in dtype or not (num_td and num_td.get_text(strip=True).isdigit()):
            continue
        a = tr.select_one("td.gall_tit a")
        title = a.get_text(" ", strip=True) if a else ""
        date_td = tr.select_one("td.gall_date")
        reply = tr.select_one("span.reply_num")
        rec = tr.select_one("td.gall_recommend")
        rows.append({
            "no": no,
            "title": title,
            "created_at": kst_to_iso(date_td.get("title", "") if date_td else ""),
            "replies": int(re.sub(r"\D", "", reply.get_text()) or 0) if reply else 0,
            "recommend": int(re.sub(r"\D", "", rec.get_text()) or 0) if rec else 0,
        })
    return rows


def parse_view(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("span.title_subject")
    body = soup.select_one("div.write_div")
    date = soup.select_one(".gall_date")
    esno = soup.select_one("input#e_s_n_o")
    rec = soup.select_one("p.up_num")
    text = body.get_text("\n", strip=True) if body else ""
    text = SIG_RE.sub("", text).strip()
    return {
        "title": title.get_text(strip=True) if title else "",
        "body": text,
        "created_at": kst_to_iso((date.get("title") or date.get_text(strip=True)) if date else ""),
        "esno": esno.get("value", "") if esno else "",
        "recommend": int(re.sub(r"\D", "", rec.get_text()) or 0) if rec else 0,
    }


class DCInsideCollector:
    def __init__(self, settings: dict):
        c = settings["collect"]
        self.cfg = settings["dcinside"]
        self.salt = c["author_salt"]
        self.http = PoliteSession(c["user_agent"], c["request_delay_sec"])

    def _comments(self, gal: dict, no: str, esno: str, title: str, group_key: str, post_iso: str) -> list[RawDoc]:
        """댓글은 페이지에 포함되지 않고 브라우저가 별도로 불러옴. 그 요청을 그대로 재현.
        (응답 형식이 바뀌면 빈 리스트를 반환하고 경고만 남김)"""
        docs = []
        for page in range(1, self.cfg["max_comment_pages"] + 1):
            r = self.http.post(
                f"{BASE}/board/comment/",
                data={"id": gal["id"], "no": no, "cmt_id": gal["id"], "cmt_no": no, "e_s_n_o": esno,
                      "comment_page": page, "sort": "", "_GALLTYPE_": GALLTYPE[gal["type"]]},
                headers={"X-Requested-With": "XMLHttpRequest", "Referer": view_url(gal, no)},
            )
            try:
                data = r.json()
            except ValueError:
                log.warning("[DC] 댓글 응답 형식이 예상과 다름 (no=%s). 댓글 수집을 건너뜁니다.", no)
                return docs
            items = data.get("comments") or []
            for c in items:
                if c.get("del_yn") == "Y" or c.get("name") == "댓글돌이":
                    continue
                memo = c.get("memo") or ""
                if "<img" in memo or "<video" in memo:   # 디시콘(이미지)만 있는 댓글
                    continue
                text = htmllib.unescape(re.sub(r"<[^>]+>", " ", memo)).strip()
                if not text:
                    continue
                docs.append(RawDoc(
                    source="dcinside", doc_id=f"{gal['id']}:{no}:c{c.get('no')}", kind="comment",
                    group_key=group_key, text=text, url=view_url(gal, no), context_title=title,
                    likes=0, created_at=kst_to_iso(c.get("reg_date", "")) or post_iso,
                    author_hash=hash_author(c.get("user_id") or c.get("ip") or c.get("name", ""), self.salt),
                    parent_id=f"{gal['id']}:{no}", trainable=True,
                ))
            total = int(data.get("total_cnt") or 0)
            if not items or len(docs) >= total:
                break
        return docs

    def _gallery(self, group: GroupConfig, gal: dict, since: datetime) -> list[RawDoc]:
        keywords = [None] if gal.get("mode", "list") == "list" else \
            list(dict.fromkeys([group.name] + group.member_names))
        seen, docs = set(), []
        for kw in keywords:
            for page in range(1, self.cfg["max_list_pages"] + 1):
                url = list_url(gal, page, kw)
                try:
                    r = self.http.get(url)
                except RobotsDisallowed:
                    log.warning("[DC] robots.txt 에서 금지된 갤러리: %s → 건너뜀", gal["id"])
                    return docs
                if r.status_code != 200:
                    log.warning("[DC] 목록 HTTP %s: %s", r.status_code, url)
                    break
                rows = parse_list(r.text)
                if not rows:
                    break
                old = 0
                for row in rows:
                    created = parse_iso(row["created_at"])
                    if created and created < since:
                        old += 1
                        continue
                    if row["no"] in seen:
                        continue
                    seen.add(row["no"])
                    docs += self._post(group, gal, row)
                log.info("[DC] %s %s p%d → 누적 %d건", gal["id"], kw or "", page, len(docs))
                if old == len(rows):   # 페이지 전체가 기간 밖이면 중단
                    break
        return docs

    def _post(self, group: GroupConfig, gal: dict, row: dict) -> list[RawDoc]:
        doc_id = f"{gal['id']}:{row['no']}"
        # 멤버 전용 갤러리의 글은 이름이 없어도 그 멤버 얘기 → 맥락 제목에 멤버명을 붙여 context_member 로 연결
        prefix = f"[{gal['member']}] " if gal.get("member") else ""
        title_doc = RawDoc(source="dcinside", doc_id=doc_id, kind="post_title", group_key=group.key,
                           text=row["title"], url=view_url(gal, row["no"]), context_title=prefix + row["title"],
                           likes=row["recommend"], created_at=row["created_at"], trainable=True)
        if row["replies"] < self.cfg["detail_min_replies"]:
            return [title_doc]
        try:
            r = self.http.get(view_url(gal, row["no"]))
        except RobotsDisallowed:
            return [title_doc]
        if r.status_code != 200:
            return [title_doc]
        v = parse_view(r.text)
        post = RawDoc(source="dcinside", doc_id=doc_id, kind="post", group_key=group.key,
                      text=f"{v['title'] or row['title']}\n{v['body']}".strip(), url=view_url(gal, row["no"]),
                      context_title=prefix + (v["title"] or row["title"]), likes=v["recommend"] or row["recommend"],
                      created_at=v["created_at"] or row["created_at"], trainable=True)
        out = [post]
        if self.cfg["fetch_comments"] and v["esno"]:
            try:
                out += self._comments(gal, row["no"], v["esno"], post.context_title, group.key, post.created_at)
            except Exception as e:  # 댓글 실패가 전체 수집을 멈추지 않도록
                log.warning("[DC] 댓글 수집 실패 no=%s: %s", row["no"], e)
        return out

    def collect(self, group: GroupConfig, since: datetime, db=None) -> list[RawDoc]:
        all_docs = []
        for gal in group.dcinside.get("galleries", []):
            docs = self._gallery(group, gal, since)
            if db is not None:
                db.upsert_docs(docs)
            all_docs += docs
        return all_docs
