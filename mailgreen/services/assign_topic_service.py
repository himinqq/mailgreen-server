import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from mailgreen.app.database import SessionLocal
from mailgreen.app.models import MailEmbedding, MajorTopicEmbedding


# 코사인 유사도 계산 함수
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


PROMOTION_ID = 5

# 유사도 기준
SIM_THRESHOLD = 0.4


def batch_assign_category():
    db: Session = SessionLocal()
    try:
        # major_topic_embedding에서 topic_id(1~4)와 벡터를 모두 가져오기
        mt_rows = db.query(
            MajorTopicEmbedding.topic_id, MajorTopicEmbedding.vector
        ).all()

        topic_ids = [r.topic_id for r in mt_rows]  # [1,2,3,4]
        topic_vecs = [
            np.array(r.vector, dtype=float) for r in mt_rows
        ]  # list of numpy arrays

        # 아직 category=NULL이고 is_deleted=False인 메일만 조회
        mail_rows = (
            db.query(MailEmbedding.id, MailEmbedding.vector, MailEmbedding.labels)
            .filter(MailEmbedding.category.is_(None), MailEmbedding.is_deleted == False)
            .all()
        )

        for mail_id, mail_vec_list, mail_labels in mail_rows:
            if "CATEGORY_PROMOTIONS" in mail_labels:
                assigned_cat = PROMOTION_ID
            elif mail_vec_list is None or len(mail_vec_list) == 0:
                assigned_cat = None
            else:
                mail_vec = np.array(mail_vec_list, dtype=float)  # (384,)

                # 각 대주제 벡터와 코사인 유사도 계산
                sims = np.array(
                    [cosine_similarity(mail_vec, tv) for tv in topic_vecs]
                )  # (4,)
                max_idx = int(np.argmax(sims))  # 0~3
                max_sim = float(sims[max_idx])

                # 기준 이상이면 해당 topic_id, 아니면 others
                if max_sim >= SIM_THRESHOLD:
                    assigned_cat = topic_ids[max_idx]  # 1~4
                else:
                    assigned_cat = None

            db.execute(
                text(
                    """
                    UPDATE mail_embeddings
                    SET category = :cat
                    WHERE id = :mid
                """
                ),
                {"cat": assigned_cat, "mid": str(mail_id)},
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
