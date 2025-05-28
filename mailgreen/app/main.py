import os
from dotenv import load_dotenv, find_dotenv
from starlette.middleware.sessions import SessionMiddleware

load_dotenv(find_dotenv())

from fastapi import FastAPI
from mailgreen.app.database import init_db
from mailgreen.controller.auth_controller import router as auth_router

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

init_db()  # 로컬
app.include_router(auth_router)
