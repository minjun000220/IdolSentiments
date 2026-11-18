import html
import re
import unicodedata

URL_RE = re.compile(r"https?://\S+|www\.\S+")
TIMESTAMP_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")          # 유튜브 "1:23"
REPEAT_JAMO_RE = re.compile(r"([ㄱ-ㅎㅏ-ㅣ])\1{2,}")                 # ㅋㅋㅋㅋ → ㅋㅋ
REPEAT_CHAR_RE = re.compile(r"(.)\1{3,}")                            # !!!!!! → !!!
DC_SIG_RE = re.compile(r"-\s*dc official App|- dc App", re.I)
SPACE_RE = re.compile(r"[ \t​　]+")


def clean(text: str) -> str:
    # NFKC는 호환 자모(ㅋ)를 조합형 자모로 바꿔버리므로 NFC 사용
    t = unicodedata.normalize("NFC", html.unescape(text or ""))
    t = URL_RE.sub(" ", t)
    t = DC_SIG_RE.sub(" ", t)
    t = TIMESTAMP_RE.sub(" ", t)
    t = REPEAT_JAMO_RE.sub(r"\1\1", t)
    t = REPEAT_CHAR_RE.sub(r"\1\1\1", t)
    t = SPACE_RE.sub(" ", t)
    t = "\n".join(line.strip() for line in t.splitlines() if line.strip())
    return t.strip()


def meaningful(text: str, min_chars: int) -> bool:
    """자음/이모지/기호만 있는 문장 제거."""
    core = re.sub(r"[^가-힣A-Za-z0-9]", "", text)
    return len(core) >= min_chars
