from mailgreen.app.config import Config as AppConfig
from fastapi import HTTPException
from google_auth_oauthlib.flow import Flow
import requests

CLIENT_ID = AppConfig.GOOGLE_CLIENT_ID
CLIENT_SECRET = AppConfig.GOOGLE_CLIENT_SECRET
REDIRECT_URI = AppConfig.GOOGLE_REDIRECT_URI

SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://mail.google.com/",
    "openid",
]


def get_google_auth_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def refresh_token(token):
    if not token or "refresh_token" not in token:
        raise HTTPException(status_code=400, detail="Refresh token이 없습니다.")
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token",
    }
    response = requests.post("https://oauth2.googleapis.com/token", data=data)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="토큰 갱신 실패")
    return response.json()
