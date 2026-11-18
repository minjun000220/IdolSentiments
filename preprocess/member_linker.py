"""문장 → 멤버/그룹 연결.

우선순위 (문장마다 하나의 방식만 적용):
  1. explicit        문장에 멤버 이름이 있음             conf = 1.0 / n명
  2. carry           앞 문장의 멤버를 이어받음           conf = 0.6 / n명
  3. context_member  영상/글 제목에 멤버가 정확히 1명    conf = 0.5
  4. explicit_group  문장에 그룹 이름 있음 (멤버 없음)  conf = 1.0
  5. context_group   그 외 (그룹 관련 수집물이므로)     conf = 0.7  ← 관련성 점수로 한 번 더 걸러짐
"""
import re
from dataclasses import dataclass

from core.config import GroupConfig

GROUP = "@group"
PARTICLES = "이랑|한테|에게|이가|이는|이도|이를|이의|님|씨|이|가|은|는|을|를|의|도|만|아|야|랑|형|오빠|언니"


@dataclass
class Link:
    target: str     # 멤버 이름 또는 "@group"
    conf: float
    method: str


def _alias_pattern(alias: str) -> str:
    esc = re.escape(alias)
    if re.fullmatch(r"[가-힣]", alias):
        # 한 글자 이름("뷔", "진"): "진짜", "뷔페" 오탐 방지 → 뒤에 한글이 없거나 조사가 붙은 경우만
        return rf"(?<![가-힣]){esc}(?=$|[^가-힣]|(?:{PARTICLES})(?![가-힣]))"
    if re.search(r"[가-힣]", alias):
        # 왼쪽에 한글이 붙어 있으면 다른 단어의 일부 ("뭐하니", "아민지") → 제외
        # 오른쪽은 조사가 붙으므로 허용 ("민지가", "민지는")
        return rf"(?<![가-힣]){esc}"
    return rf"(?<![A-Za-z]){esc}(?![A-Za-z])"


class MemberLinker:
    def __init__(self, group: GroupConfig, conf: dict):
        self.conf = conf
        self.members = {}
        for m in group.members:
            pat = re.compile("|".join(_alias_pattern(a) for a in sorted(m.aliases, key=len, reverse=True)),
                             re.IGNORECASE)
            excl = re.compile("|".join(m.exclude_patterns)) if m.exclude_patterns else None
            self.members[m.name] = (pat, excl)
        self.group_pat = re.compile(
            "|".join(_alias_pattern(a) for a in sorted(group.aliases, key=len, reverse=True)), re.IGNORECASE)

    def find_members(self, text: str) -> list[str]:
        found = []
        for name, (pat, excl) in self.members.items():
            t = excl.sub(" ", text) if excl else text
            if pat.search(t):
                found.append(name)
        return found

    def has_group(self, text: str) -> bool:
        return bool(self.group_pat.search(text))

    def link_doc(self, sentences: list[str], context_title: str) -> list[list[Link]]:
        c = self.conf
        ctx_members = self.find_members(context_title or "")
        prev_members: list[str] = []
        out = []
        for s in sentences:
            ms = self.find_members(s)
            if ms:
                links = [Link(m, c["explicit"] / len(ms), "explicit") for m in ms]
                prev_members = ms
            elif prev_members:
                links = [Link(m, c["carry"] / len(prev_members), "carry") for m in prev_members]
                prev_members = []          # 한 문장까지만 이어받음
            elif len(ctx_members) == 1:
                links = [Link(ctx_members[0], c["context_member"], "context_member")]
            elif self.has_group(s):
                links = [Link(GROUP, c["explicit_group"], "explicit_group")]
            else:
                links = [Link(GROUP, c["context_group"], "context_group")]
            out.append(links)
        return out
