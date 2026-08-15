from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routes import admin, ai_config, auth, integrations, lesson_ai, tasks, uploads


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


app = FastAPI(title="Teaching Design System API", lifespan=lifespan)

default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:54536",
    "http://127.0.0.1:54536",
]
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
] or default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(tasks.router)
app.include_router(uploads.router)
app.include_router(auth.router)
app.include_router(admin.admin_router)
app.include_router(admin.public_router)
app.include_router(ai_config.router)
app.include_router(lesson_ai.router)
app.include_router(integrations.router)
