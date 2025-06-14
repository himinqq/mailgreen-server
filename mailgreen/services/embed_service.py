from sentence_transformers import SentenceTransformer
from typing import List

_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


def get_embedding(texts: List[str]) -> List[float]:
    inputs = [t if t else "" for t in texts]  # None 혹은 빈 텍스트를 빈 문자열로 대체
    vecs = _model.encode(inputs)
    return [v.tolist() for v in vecs]
