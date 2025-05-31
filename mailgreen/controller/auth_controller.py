from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from mailgreen.app.database import get_db
from authlib.integrations.starlette_client import OAuth
from mailgreen.app.models import User, UserCredentials
import logging, os
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile https://www.googleapis.com/auth/gmail.modify"
    },
    authorize_params={"access_type": "offline", "prompt": "consent"},
)


@router.get("/google")
async def login_via_google(request: Request):
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
        resp = await oauth.google.get(
            "https://www.googleapis.com/oauth2/v3/userinfo", token=token
        )
        info = resp.json()

        # 1. 사용자 정보 등록
        user = db.query(User).filter(User.google_sub == info["sub"]).first()
        if not user:
            user = User(
                google_sub=info["sub"],
                email=info["email"],
                name=info.get("name"),
                picture_url=info.get("picture"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 2. 사용자 인증 정보 저장 또는 갱신
        creds = (
            db.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
        )
        expiry_time = datetime.utcnow() + timedelta(seconds=token["expires_in"])
        if creds:
            creds.access_token = token["access_token"]
            creds.refresh_token = token.get("refresh_token", creds.refresh_token)
            creds.expiry = expiry_time
        else:
            creds = UserCredentials(
                user_id=user.id,
                access_token=token["access_token"],
                refresh_token=token.get("refresh_token"),
                expiry=expiry_time,
            )
            db.add(creds)
        db.commit()

        redirect_url = f"{os.getenv('CLIENT_REDIRECT_URI')}/login/success?id={user.id}&name={user.name}&email={user.email}"
        return RedirectResponse(url=redirect_url)
    except Exception:
        logger.exception("Google 인증 오류")
        raise HTTPException(status_code=500, detail="Google 인증 실패")
