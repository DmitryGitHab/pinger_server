"""Импорт и экспорт списка IP-адресов в CSV."""

import csv
import io
import re

from fastapi import UploadFile

from config import IP_REGEX
from database import get_db


async def export_ips_to_csv() -> str:
    """Возвращает содержимое CSV со всеми IP и их метриками."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM ip_addresses")
        rows = await cursor.fetchall()
        column_names = [d[0] for d in cursor.description]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(column_names)
    writer.writerows(rows)
    buffer.seek(0)
    return buffer.getvalue()


async def import_ips_from_csv(file: UploadFile) -> int:
    """Импортирует IP из загруженного CSV-файла (только первый столбец).

    Невалидные и уже существующие IP пропускаются молча.
    Возвращает количество реально добавленных адресов.
    """
    content = (await file.read()).decode("utf-8").splitlines()
    reader = csv.reader(content)

    added = 0
    async with get_db() as db:
        for row in reader:
            if not row:
                continue

            ip = row[0].strip()
            if not re.match(IP_REGEX, ip):
                continue

            cursor = await db.execute(
                "SELECT 1 FROM ip_addresses WHERE ip = ?", (ip,)
            )
            if await cursor.fetchone():
                continue

            await db.execute(
                """
                INSERT INTO ip_addresses (ip, ping, packet_loss, packet_received, last_successful_ping)
                VALUES (?, NULL, NULL, NULL, NULL)
                """,
                (ip,),
            )
            added += 1

        await db.commit()

    return added
