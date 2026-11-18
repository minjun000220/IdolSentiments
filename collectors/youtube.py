"""YouTube Data API v3 수집기.

할당량(하루 10,000 유닛):
  search.list = 100 / commentThreads.list = 1 / playlistItems.list = 1 / channels.list = 1
→ 검색은 최소로, 댓글 수집에 유닛을 쓰는 구조.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

import requests

from collectors.base import hash_author
from core.config import GroupConfig
from core.timeutil import now_utc, parse_iso, to_iso
from core.types import RawDoc
from storage.db import DB

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3/"
COST = {"search": 100, "commentThreads": 1, "playlistItems": 1, "channels": 1, "videos": 1}
PT = timezone(timedelta(hours=-8))  # 할당량은 태평양 시간 자정에 초기화 (근사치)


class QuotaExceeded(Exception):
    pass


class YouTubeCollector:
    def __init__(self, settings: dict, db: DB, api_key: str):
        if not api_key:
            raise SystemExit("YOUTUBE_API_KEY 가 없습니다. .env 파일에 YOUTUBE_API_KEY=AIza... 를 넣어주세요.")
        self.cfg = settings["youtube"]
        self.salt = settings["collect"]["author_salt"]
        self.db = db
        self.s = requests.Session()
        # 키를 URL 대신 헤더로 보냄 (로그에 키가 남지 않도록)
        self.s.headers["X-goog-api-key"] = api_key

    # ---------- 할당량 ----------
    @staticmethod
    def _day() -> str:
        return datetime.now(PT).strftime("%Y-%m-%d")

    def remaining(self) -> int:
        return self.cfg["daily_quota"] - self.cfg["quota_reserve"] - self.db.yt_quota_used(self._day())

    def _call(self, endpoint: str, **params) -> dict | None:
        cost = COST[endpoint]
        if self.remaining() < cost:
            raise QuotaExceeded(f"오늘 남은 할당량 {self.remaining()} < {cost}")
        r = self.s.get(API + endpoint, params=params, timeout=20)
        self.db.yt_quota_add(self._day(), cost)
        if r.status_code == 200:
            return r.json()
        try:
            reason = r.json()["error"]["errors"][0]["reason"]
        except Exception:
            reason = r.text[:200]
        if reason in ("quotaExceeded", "dailyLimitExceeded"):
            raise QuotaExceeded(reason)
        if reason in ("commentsDisabled", "videoNotFound", "forbidden"):
            log.info("건너뜀 (%s): %s", reason, params.get("videoId", ""))
            return None
        raise RuntimeError(f"YouTube API 오류 {r.status_code}: {reason}")

    # ---------- 영상 찾기 ----------
    def _queries(self, group: GroupConfig) -> list[str]:
        if group.youtube.get("queries"):
            return group.youtube["queries"]
        g = group.name
        latin = next((a for a in group.aliases if re.fullmatch(r"[A-Za-z0-9 .&'\-]+", a)), None)
        qs = [g] + ([latin] if latin else [])
        for m in group.member_names:
            qs += [f"{g} {m}", f"{g} {m} 직캠"]
        return list(dict.fromkeys(qs))

    def find_videos(self, group: GroupConfig, since: datetime) -> dict[str, dict]:
        videos: dict[str, dict] = {}

        # 1) 공식 채널 업로드 목록 (저렴)
        for ch in group.youtube.get("channel_ids", []):
            data = self._call("channels", part="contentDetails", id=ch)
            if not data or not data.get("items"):
                continue
            uploads = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            token = None
            for _ in range(4):
                data = self._call("playlistItems", part="snippet", playlistId=uploads, maxResults=50,
                                  **({"pageToken": token} if token else {}))
                if not data:
                    break
                stop = False
                for it in data.get("items", []):
                    sn = it["snippet"]
                    pub = parse_iso(sn.get("publishedAt", ""))
                    if pub and pub < since:
                        stop = True
                        continue
                    vid = (sn.get("resourceId") or {}).get("videoId")
                    if not vid:
                        continue
                    videos[vid] = {"title": sn.get("title", ""), "published_at": sn.get("publishedAt", "")}
                token = data.get("nextPageToken")
                if stop or not token:
                    break

        # 2) 검색 (비쌈: 100 유닛)
        for q in self._queries(group)[: self.cfg["max_searches"]]:
            data = self._call("search", part="snippet", q=q, type="video", order="relevance",
                              maxResults=self.cfg["videos_per_search"], publishedAfter=to_iso(since) + "Z",
                              regionCode="KR", relevanceLanguage="ko")
            for it in (data or {}).get("items", []):
                vid = (it.get("id") or {}).get("videoId")   # 채널/재생목록 등 영상이 아닌 결과는 건너뜀
                if not vid:
                    continue
                sn = it.get("snippet") or {}
                videos.setdefault(vid, {"title": sn.get("title", ""), "published_at": sn.get("publishedAt", "")})
            log.info("검색 '%s' → 누적 영상 %d개", q, len(videos))
        return videos

    # ---------- 댓글 ----------
    def _comment_doc(self, group: GroupConfig, sn: dict, cid: str, vid: str, title: str, parent="") -> RawDoc:
        return RawDoc(
            source="youtube", doc_id=cid, kind="comment", group_key=group.key,
            text=sn.get("textDisplay") or sn.get("textOriginal") or "",
            url=f"https://www.youtube.com/watch?v={vid}&lc={cid}", context_title=title,
            likes=int(sn.get("likeCount", 0)), created_at=to_iso(parse_iso(sn.get("publishedAt")) or now_utc()),
            author_hash=hash_author((sn.get("authorChannelId") or {}).get("value", ""), self.salt),
            parent_id=parent or vid, trainable=True,
        )

    def fetch_comments(self, group: GroupConfig, vid: str, title: str) -> list[RawDoc]:
        docs, token = [], None
        for _ in range(self.cfg["max_comment_pages"]):
            data = self._call("commentThreads", part="snippet,replies", videoId=vid, maxResults=100,
                              order=self.cfg["comment_order"], textFormat="plainText",
                              **({"pageToken": token} if token else {}))
            if not data:
                break
            for th in data.get("items", []):
                top = th["snippet"]["topLevelComment"]
                docs.append(self._comment_doc(group, top["snippet"], top["id"], vid, title))
                for rep in (th.get("replies") or {}).get("comments", []):
                    docs.append(self._comment_doc(group, rep["snippet"], rep["id"], vid, title, parent=top["id"]))
            token = data.get("nextPageToken")
            if not token:
                break
        return docs

    # ---------- 전체 ----------
    def collect(self, group: GroupConfig, since: datetime) -> list[RawDoc]:
        log.info("[YouTube] 남은 할당량: %d", self.remaining())
        all_docs: list[RawDoc] = []
        try:
            videos = self.find_videos(group, since)
            refetch_after = to_iso(now_utc() - timedelta(days=self.cfg["refetch_after_days"]))
            for i, (vid, meta) in enumerate(videos.items(), 1):
                if self.db.yt_recently_fetched(vid, refetch_after):
                    continue
                docs = self.fetch_comments(group, vid, meta["title"])
                self.db.upsert_docs(docs)  # 영상 단위로 바로 저장 (중간에 끊겨도 보존)
                self.db.yt_mark_fetched(vid, group.key, meta["title"], meta["published_at"], to_iso(now_utc()))
                all_docs += docs
                log.info("[YouTube] %d/%d %s → 댓글 %d개", i, len(videos), meta["title"][:40], len(docs))
        except QuotaExceeded as e:
            log.warning("[YouTube] 할당량 소진으로 중단: %s (내일 이어서 실행하세요)", e)
        return all_docs
