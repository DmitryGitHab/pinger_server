"""Асинхронный доступ к SQLite.

Оригинальный database.py использовал синхронный sqlite3 и нигде не
импортировался — main.py дублировал логику подключения через aiosqlite
прямо в каждом эндпоинте. Здесь это собрано в одном месте и используется
всеми роутерами и сервисами.
"""

from contextlib import asynccontextmanager

import aiosqlite

from config import DB_PATH


async def init_db() -> None:
    """Создать таблицу ip_addresses, если её ещё нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ip_addresses (
                ip TEXT PRIMARY KEY,
                ping REAL,
                packet_loss REAL,
                packet_received REAL,
                last_successful_ping TEXT
            )
            """
        )
        await db.commit()


@asynccontextmanager
async def get_db():
    """Асинхронный контекстный менеджер для подключения к БД.

    Использование:
        async with get_db() as db:
            await db.execute(...)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        yield db


async def fetch_all_ips() -> list[dict]:
    """Возвращает все строки ip_addresses в виде списка dict.

    Общая логика, которая раньше была продублирована и в REST-эндпоинте
    GET /ip/, и в WebSocket-обработчике.
    """
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM ip_addresses")
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in rows]
