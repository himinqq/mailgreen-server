from sentence_transformers import SentenceTransformer
from typing import List

_model = SentenceTransformer("snunlp/KR-SBERT-V40K-klueNLI-augSTS")


def get_embedding(text: str) -> List[float]:
    if not text:
        return []
    vec = _model.encode(text)
    return vec.tolist()
