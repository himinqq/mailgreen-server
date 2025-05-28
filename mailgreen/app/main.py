import os
from dotenv import load_dotenv, find_dotenv
from starlette.middleware.sessions import SessionMiddleware

load_dotenv(find_dotenv())

from fastapi import FastAPI
from mailgreen.app.database import init_db

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

init_db()  # 로컬
