from dataclasses import dataclass


@dataclass
class RawDoc:
    """수집된 원문 1건 (게시글, 댓글, 제목만 있는 글 등)."""
    source: str             # youtube | dcinside
    doc_id: str             # 출처 안에서 유일한 ID
    kind: str               # post | post_title | comment
    text: str
    group_key: str = ""
    url: str = ""
    context_title: str = ""  # 영상 제목 / 게시글 제목 (멤버 연결에 사용)
    likes: int = 0
    created_at: str = ""     # UTC ISO8601 "YYYY-MM-DDTHH:MM:SS"
    author_hash: str = ""
    parent_id: str = ""
    trainable: bool = True   # 학습 데이터로 써도 되는지

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.doc_id}"
