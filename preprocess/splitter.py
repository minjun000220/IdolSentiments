import logging
import re

log = logging.getLogger(__name__)

try:
    import kss  # 선택 의존성. 설치되어 있으면 더 정확한 한국어 문장 분리
    _HAS_KSS = True
except Exception:
    _HAS_KSS = False

_FALLBACK_RE = re.compile(r"(?<=[.!?。~])\s+|\n+|(?<=ㅋㅋ)\s+|(?<=ㅠㅠ)\s+")


def split_sentences(text: str, max_chars: int = 300) -> list[str]:
    if not text:
        return []
    parts: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if _HAS_KSS and len(para) > 40:
            try:
                parts += kss.split_sentences(para)
                continue
            except Exception as e:
                log.debug("kss 실패, 정규식으로 대체: %s", e)
        parts += _FALLBACK_RE.split(para)
    out = []
    for p in parts:
        p = p.strip()
        while len(p) > max_chars:      # 너무 긴 문장은 잘라서 처리
            out.append(p[:max_chars])
            p = p[max_chars:]
        if p:
            out.append(p)
    return out
