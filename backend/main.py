import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load local settings without overriding variables injected by production.
load_dotenv(override=False)

from api.routes.auth import router as auth_router
from api.routes.benchmark import router as benchmark_router
from api.routes.testing import router as testing_router

app = FastAPI(title="ZakLang API")

app.include_router(testing_router)
app.include_router(auth_router)
app.include_router(benchmark_router)

FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)