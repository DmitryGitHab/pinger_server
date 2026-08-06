"""Фоновая задача: пингует все сохранённые IP параллельно и пишет результат в БД."""

import asyncio
import logging
from datetime import datetime

import aioping

from config import PING_INTERVAL, PING_TIMEOUT
from database import get_db

logger = logging.getLogger(__name__)


async def ping_ip(ip: str) -> None:
    """Пингует один IP и сохраняет результат в БД."""
    try:
        delay = await aioping.ping(ip, timeout=PING_TIMEOUT)
        ping_ms = delay * 1000
        packet_loss, packet_received = 0, 100
        last_successful_ping = datetime.now()
    except Exception as exc:
        logger.debug("Ping failed for %s: %s", ip, exc)
        ping_ms = None
        packet_loss, packet_received = 100, 0
        last_successful_ping = None

    async with get_db() as db:
        await db.execute(
            """
            UPDATE ip_addresses
            SET ping = ?, packet_loss = ?, packet_received = ?, last_successful_ping = ?
            WHERE ip = ?
            """,
            (ping_ms, packet_loss, packet_received, last_successful_ping, ip),
        )
        await db.commit()


async def ping_all_loop() -> None:
    """Бесконечный цикл: читает список IP из БД и пингует их все параллельно.

    asyncio.gather запускает пинг всех адресов одновременно, а не по очереди —
    иначе время одного цикла росло бы линейно с числом серверов.
    """
    while True:
        async with get_db() as db:
            cursor = await db.execute("SELECT ip FROM ip_addresses")
            rows = await cursor.fetchall()

        if rows:
            await asyncio.gather(*(ping_ip(row[0]) for row in rows))

        await asyncio.sleep(PING_INTERVAL)
