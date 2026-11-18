import hashlib
import logging

import numpy as np

log = logging.getLogger(__name__)


def text_hash(t: str) -> str:
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


class SbertEncoder:
    """sentence-transformers 래퍼. 정규화된 임베딩을 반환하고 DB에 캐시한다."""

    def __init__(self, model_name: str, db=None, device: str | None = None, batch_size: int = 64):
        from sentence_transformers import SentenceTransformer  # 무거운 import는 필요할 때만
        log.info("SBERT 모델 로딩: %s", model_name)
        self.model = SentenceTransformer(model_name, device=device)
        self.name = model_name
        self.db = db
        self.batch_size = batch_size

    def _encode_raw(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                 show_progress_bar=len(texts) > 500, convert_to_numpy=True).astype(np.float32)

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)
        hashes = [text_hash(t) for t in texts]
        cached = self.db.get_embeddings(self.name, list(set(hashes))) if self.db else {}
        missing = list({h: t for h, t in zip(hashes, texts) if h not in cached}.items())
        if missing:
            log.info("임베딩 계산: %d개 (캐시 %d개)", len(missing), len(cached))
            vecs = self._encode_raw([t for _, t in missing])
            new = {h: v for (h, _), v in zip(missing, vecs)}
            if self.db:
                self.db.put_embeddings(self.name, new)
            cached.update(new)
        return np.stack([cached[h] for h in hashes])
