"""CRUD-эндпоинты для управления списком мониторимых IP."""

from fastapi import APIRouter, HTTPException

from database import fetch_all_ips, get_db
from models import IPCreate, IPInfo

router = APIRouter(prefix="/ip", tags=["ip"])


@router.get("/", response_model=list[IPInfo])
async def list_ips():
    return await fetch_all_ips()


@router.post("/", response_model=IPInfo, status_code=201)
async def add_ip(payload: IPCreate):
    async with get_db() as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO ip_addresses (ip, ping, packet_loss, packet_received, last_successful_ping)
            VALUES (?, NULL, NULL, NULL, NULL)
            """,
            (payload.ip,),
        )
        await db.commit()
    return IPInfo(ip=payload.ip)


@router.get("/{ip}", response_model=IPInfo)
async def get_ip(ip: str):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM ip_addresses WHERE ip = ?", (ip,))
        row = await cursor.fetchone()
        columns = [d[0] for d in cursor.description] if row else []

    if row is None:
        raise HTTPException(status_code=404, detail="IP not found")
    return dict(zip(columns, row))


@router.put("/{old_ip}", response_model=IPInfo)
async def edit_ip(old_ip: str, payload: IPCreate):
    async with get_db() as db:
        cursor = await db.execute("SELECT 1 FROM ip_addresses WHERE ip = ?", (old_ip,))
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Old IP not found")

        await db.execute(
            "UPDATE ip_addresses SET ip = ? WHERE ip = ?",
            (payload.ip, old_ip),
        )
        await db.commit()

    return IPInfo(ip=payload.ip)


@router.delete("/{ip}", status_code=204)
async def delete_ip(ip: str):
    async with get_db() as db:
        await db.execute("DELETE FROM ip_addresses WHERE ip = ?", (ip,))
        await db.commit()
