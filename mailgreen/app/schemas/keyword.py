from pydantic import BaseModel


class TopKeywordOut(BaseModel):
    topic_id: int
    description: str
    count: int

    class Config:
        orm_mode = True
