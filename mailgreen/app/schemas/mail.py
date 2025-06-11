from pydantic import BaseModel
from typing import List


class MailOut(BaseModel):
    id: str
    subject: str | None
    snippet: str | None
    received_at: str
    is_read: bool | None
    starred: bool

    class Config:
        from_attributes = True


class DeleteMailsRequest(BaseModel):
    message_ids: List[str]
    confirm: bool = False  # false면 삭제하지 않고 추정만
    delete_protected_sender: bool = False
