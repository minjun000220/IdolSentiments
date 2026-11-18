from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def load_settings(path: Path | None = None) -> dict:
    with open(path or CONFIG_DIR / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_anchors(path: Path | None = None) -> dict:
    with open(path or CONFIG_DIR / "anchors.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Member:
    name: str
    aliases: list[str]
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class GroupConfig:
    key: str                 # 파일명 (예: newjeans)
    name: str
    aliases: list[str]
    members: list[Member]
    youtube: dict = field(default_factory=dict)
    dcinside: dict = field(default_factory=dict)

    @property
    def member_names(self) -> list[str]:
        return [m.name for m in self.members]


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _parse_group(key: str, raw: dict) -> GroupConfig:
    g = raw.get("group", {})
    members = [
        Member(name=name, aliases=list(dict.fromkeys([name] + (m or {}).get("aliases", []))),
               exclude_patterns=(m or {}).get("exclude_patterns", []))
        for name, m in (raw.get("members") or {}).items()
    ]
    return GroupConfig(
        key=key,
        name=g.get("name", key),
        aliases=list(dict.fromkeys([g.get("name", key)] + g.get("aliases", []))),
        members=members,
        youtube=raw.get("youtube") or {},
        dcinside=raw.get("dcinside") or {},
    )


def list_groups() -> list[GroupConfig]:
    out = []
    for p in sorted((CONFIG_DIR / "groups").glob("*.yaml")):
        with open(p, encoding="utf-8") as f:
            out.append(_parse_group(p.stem, yaml.safe_load(f)))
    return out


def find_group(query: str) -> GroupConfig | None:
    """파일명 또는 그룹 별칭으로 저장된 그룹 설정을 찾는다. ('뉴진스', 'NewJeans', 'newjeans' 모두 가능)"""
    q = _norm(query)
    for g in list_groups():
        if q == _norm(g.key) or q in {_norm(a) for a in g.aliases}:
            return g
    return None


def load_group(query: str) -> GroupConfig:
    g = find_group(query)
    if g is None:
        raise SystemExit(f"'{query}' 그룹 설정이 없습니다. `python main.py setup {query}` 로 만들 수 있습니다.")
    return g


def resolve_group(query: str, settings: dict, assume_yes: bool = False) -> GroupConfig:
    """저장된 설정이 있으면 사용, 없으면 위키/디시에서 자동으로 찾아 만든다."""
    g = find_group(query)
    if g is not None:
        return g
    from discovery.builder import auto_setup
    return auto_setup(query, settings, assume_yes=assume_yes)
