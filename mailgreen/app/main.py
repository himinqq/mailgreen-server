import os
from dotenv import load_dotenv, find_dotenv
from starlette.middleware.sessions import SessionMiddleware

load_dotenv(find_dotenv())

from fastapi import FastAPI
from mailgreen.controller.auth_controller import router as auth_router
from mailgreen.controller.mail_controller import router as mail_router

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

app.include_router(auth_router)
app.include_router(mail_router)
