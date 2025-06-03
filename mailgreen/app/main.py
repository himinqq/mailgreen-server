import os
from dotenv import load_dotenv, find_dotenv
from starlette.middleware.sessions import SessionMiddleware


load_dotenv(find_dotenv())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mailgreen.controller.auth_controller import router as auth_router
from mailgreen.controller.mail_controller import router as mail_router
from mailgreen.controller.sender_controller import router as sender_router
from mailgreen.controller.keyword_controller import router as keyword_router

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

app.include_router(auth_router)
app.include_router(mail_router)
app.include_router(sender_router)
app.include_router(keyword_router)
