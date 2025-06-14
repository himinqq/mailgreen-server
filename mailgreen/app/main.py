import os
import logging
from dotenv import load_dotenv, find_dotenv
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()
numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)

logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

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
    carbon_router,
    subscription_router,
]

for r in routers:
    app.include_router(r)
