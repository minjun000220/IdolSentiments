from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    """UTC 기준 'YYYY-MM-DDTHH:MM:SS' 문자열로 변환."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def kst_to_iso(s: str, fmts=("%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M",
                             "%Y.%m.%d", "%Y-%m-%d")) -> str:
    """한국 시간 문자열 → UTC ISO. 실패 시 빈 문자열."""
    s = (s or "").strip()
    for f in fmts:
        try:
            return to_iso(datetime.strptime(s, f).replace(tzinfo=KST))
        except ValueError:
            continue
    # 연도 없는 형식 (예: 디시 댓글 "11.16 17:20:11")
    for f in ("%m.%d %H:%M:%S", "%m.%d %H:%M"):
        try:
            d = datetime.strptime(s, f)
            now = now_utc().astimezone(KST)
            d = d.replace(year=now.year, tzinfo=KST)
            if d > now + timedelta(days=1):
                d = d.replace(year=now.year - 1)
            return to_iso(d)
        except ValueError:
            continue
    return ""


def age_days(iso: str, ref: datetime | None = None) -> float:
    dt = parse_iso(iso)
    if dt is None:
        return 0.0
    ref = ref or now_utc()
    return max(0.0, (ref - dt).total_seconds() / 86400)
