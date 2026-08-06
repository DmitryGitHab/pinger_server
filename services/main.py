"""Точка входа приложения: сборка FastAPI, роутеров и фоновых задач.

Вся бизнес-логика (пинг, CSV, работа с БД) вынесена в services/ и database.py,
все HTTP/WS-маршруты — в routers/. main.py отвечает только за "склейку".
"""

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import csv_router, ip_router, ws_router
from services.ping_service import ping_all_loop

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Pinger Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: заменить на конкретный origin фронтенда в продакшене
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ip_router.router)
app.include_router(ws_router.router)
app.include_router(csv_router.router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")


@app.on_event("startup")
async def on_startup():
    await init_db()
    asyncio.create_task(ping_all_loop())
