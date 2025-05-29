from sentence_transformers import SentenceTransformer
from typing import List

_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_embedding(text: str) -> List[float]:
    if not text:
        return []
    vec = _model.encode(text)
    return vec.tolist()
