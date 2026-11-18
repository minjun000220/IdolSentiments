import hashlib
import logging
import random
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

log = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    pass


class PoliteSession:
    """요청 간격 유지 + robots.txt 준수 + 재시도를 담당하는 공통 HTTP 세션."""

    def __init__(self, user_agent: str, delay_sec: float = 2.5, max_retries: int = 3):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent, "Accept-Language": "ko-KR,ko;q=0.9"})
        self.user_agent = user_agent
        self.delay = delay_sec
        self.max_retries = max_retries
        self._last = 0.0
        self._robots: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.s.get(base + "/robots.txt", timeout=10)
                rp.parse(r.text.splitlines() if r.ok else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[base] = rp
        rp = self._robots[base]
        return rp.can_fetch(self.user_agent, url) if rp else True

    def _wait(self):
        gap = self.delay + random.uniform(0, self.delay * 0.4)
        dt = time.monotonic() - self._last
        if dt < gap:
            time.sleep(gap - dt)
        self._last = time.monotonic()

    def request(self, method: str, url: str, **kw) -> requests.Response:
        if not self.allowed(url):
            raise RobotsDisallowed(url)
        kw.setdefault("timeout", 20)
        for attempt in range(self.max_retries):
            self._wait()
            try:
                r = self.s.request(method, url, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                return r
            except requests.RequestException as e:
                backoff = 2 ** attempt * 3
                log.warning("요청 실패 (%s) %s → %ds 후 재시도", e, url, backoff)
                time.sleep(backoff)
        raise RuntimeError(f"요청 반복 실패: {url}")

    def get(self, url: str, **kw):
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw):
        return self.request("POST", url, **kw)


def hash_author(author: str, salt: str) -> str:
    """작성자 식별자는 저장하지 않고, 도배 탐지용 해시만 남긴다."""
    if not author:
        return ""
    return hashlib.sha256(f"{salt}:{author}".encode()).hexdigest()[:16]
