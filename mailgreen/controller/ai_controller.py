from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from mailgreen.app.database import get_db
from mailgreen.services.ai_service import process_ai_request, preview_action, confirm_action

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/ask")
async def ai_ask(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    user_id = body.get("user_id")
    prompt = body.get("prompt")
    result = await process_ai_request(user_id, prompt, db)
    return result

# @router.post("/preview_action")
# async def ai_preview_action(request: Request, db: Session = Depends(get_db)):
#     body = await request.json()
#     user_id = body.get("user_id")
#     action = body.get("action")
#     filter_ = body.get("filter", {})
#     result = preview_action(db, user_id, action, filter_)
#     return result

# @router.post("/confirm_action")
# async def ai_confirm_action(request: Request, db: Session = Depends(get_db)):
#     body = await request.json()
#     user_id = body.get("user_id")
#     action = body.get("action")
#     message_ids = body.get("message_ids", [])
#     result = confirm_action(db, user_id, action, message_ids)
#     return result 