import os
from dotenv import load_dotenv, find_dotenv
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(find_dotenv())
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

from mailgreen.controller import *

routers = [
    auth_router,
    mail_router,
    sender_router,
    keyword_router,
    trash_router,
    star_router,
    carbon_router
]

for r in routers:
    app.include_router(r)

