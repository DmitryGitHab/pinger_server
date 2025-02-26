from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import aiosqlite
import asyncio
import csv
import io
import re
import aioping

app = FastAPI()

# Регулярное выражение для валидации IPv4
IP_REGEX = r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$"


# Функция для валидации IP-адреса
def validate_ip(ip: str) -> bool:
    return re.match(IP_REGEX, ip) is not None


# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все источники
    allow_methods=["*"],  # Разрешить все методы
    allow_headers=["*"],  # Разрешить все заголовки
)


# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect('ip_addresses.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ip_addresses (
                ip TEXT PRIMARY KEY,
                ping REAL,
                packet_loss REAL,
                packet_received REAL,
                last_successful_ping TEXT
            )
        ''')
        await db.commit()


# Отдача статических файлов (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# Маршрут для главной страницы
@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")


# WebSocket для обновления данных в реальном времени
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")  # Логирование
    try:
        while True:
            ips = await get_all_ips()
            print("Sending data:", ips)  # Логирование
            await websocket.send_json(jsonable_encoder(ips))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("WebSocket disconnected")


# Функция для пингования IP-адреса
async def ping_ip(ip: str):
    try:
        # Используем aioping для асинхронного пингования
        delay = await aioping.ping(ip, timeout=2)  # Пинг с таймаутом 4 секунды
        packet_loss = 0
        packet_received = 100
        last_successful_ping = datetime.now()
        delay_ms = delay * 1000  # Преобразуем секунды в миллисекунды
    except Exception as e:
        print(f"Error pinging {ip}: {e}")
        delay_ms = None
        packet_loss = 100
        packet_received = 0
        last_successful_ping = None

    async with aiosqlite.connect('ip_addresses.db') as db:
        await db.execute('''
            UPDATE ip_addresses
            SET ping = ?, packet_loss = ?, packet_received = ?, last_successful_ping = ?
            WHERE ip = ?
        ''', (delay_ms, packet_loss, packet_received, last_successful_ping, ip))
        await db.commit()


async def start_pinging():
    while True:
        async with aiosqlite.connect('ip_addresses.db') as db:
            cursor = await db.execute('SELECT ip FROM ip_addresses')
            ips = await cursor.fetchall()  # Возвращает список кортежей

        # Создаем список задач для пингования
        ping_tasks = [ping_ip(ip[0]) for ip in ips]

        # Запускаем все задачи одновременно
        await asyncio.gather(*ping_tasks)

        await asyncio.sleep(1)  # Пинговать каждые 10 секунд


# Запуск задачи для пингования
@app.on_event("startup")
async def startup():
    await init_db()
    asyncio.create_task(start_pinging())


# Остальные маршруты
@app.post("/ip/", response_model=dict)
async def add_ip(ip_info: dict):
    if not validate_ip(ip_info['ip']):
        raise HTTPException(status_code=400, detail="Invalid IP address format")

    async with aiosqlite.connect('ip_addresses.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO ip_addresses (ip, ping, packet_loss, packet_received, last_successful_ping)
            VALUES (?, ?, ?, ?, ?)
        ''', (ip_info['ip'], ip_info.get('ping'), ip_info.get('packet_loss'), ip_info.get('packet_received'),
              ip_info.get('last_successful_ping')))
        await db.commit()
    return ip_info


@app.get("/ip/{ip}", response_model=dict)
async def get_ip(ip: str):
    async with aiosqlite.connect('ip_addresses.db') as db:
        cursor = await db.execute('SELECT * FROM ip_addresses WHERE ip = ?', (ip,))
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="IP not found")
    return dict(row)


@app.delete("/ip/{ip}")
async def delete_ip(ip: str):
    async with aiosqlite.connect('ip_addresses.db') as db:
        await db.execute('DELETE FROM ip_addresses WHERE ip = ?', (ip,))
        await db.commit()
    return {"message": "IP deleted"}


@app.put("/ip/{old_ip}", response_model=dict)
async def edit_ip(old_ip: str, new_ip_info: dict):
    if not validate_ip(new_ip_info['ip']):
        raise HTTPException(status_code=400, detail="Invalid IP address format")

    async with aiosqlite.connect('ip_addresses.db') as db:
        # Проверяем, существует ли старый IP
        cursor = await db.execute('SELECT * FROM ip_addresses WHERE ip = ?', (old_ip,))
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Old IP not found")

        # Обновляем IP
        await db.execute('''
            UPDATE ip_addresses
            SET ip = ?, ping = ?, packet_loss = ?, packet_received = ?, last_successful_ping = ?
            WHERE ip = ?
        ''', (
        new_ip_info['ip'], new_ip_info.get('ping'), new_ip_info.get('packet_loss'), new_ip_info.get('packet_received'),
        new_ip_info.get('last_successful_ping'), old_ip))
        await db.commit()
    return new_ip_info


@app.get("/ip/")
async def get_all_ips():
    async with aiosqlite.connect('ip_addresses.db') as db:
        cursor = await db.execute('SELECT * FROM ip_addresses')
        rows = await cursor.fetchall()
        # Получаем имена столбцов
        column_names = [description[0] for description in cursor.description]
        # Создаем список словарей
        ips = [dict(zip(column_names, row)) for row in rows]
    # print("IPs from database:", ips)  # Логирование
    return ips


# Экспорт данных в CSV
@app.get("/export-csv/")
async def export_csv():
    async with aiosqlite.connect('ip_addresses.db') as db:
        cursor = await db.execute('SELECT * FROM ip_addresses')
        rows = await cursor.fetchall()
        # Получаем имена столбцов
        column_names = [description[0] for description in cursor.description]

    # Создаем CSV-файл в памяти
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(column_names)  # Заголовки
    for row in rows:
        writer.writerow(row)  # Записываем строки как кортежи

    # Возвращаем CSV-файл как ответ
    output.seek(0)
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=ip_addresses.csv"})


# Импорт данных из CSV (только IP-адреса)
@app.post("/import-csv/")
async def import_csv(file: UploadFile = File(...)):
    content = await file.read()
    content = content.decode("utf-8").splitlines()
    reader = csv.reader(content)

    async with aiosqlite.connect('ip_addresses.db') as db:
        for row in reader:
            ip = row[0]  # Берем только первый столбец (IP-адрес)
            if not validate_ip(ip):
                print(f"Skipping invalid IP: {ip}")
                continue  # Пропускаем невалидные IP-адреса

            # Проверяем, существует ли уже такой IP в базе
            cursor = await db.execute('SELECT ip FROM ip_addresses WHERE ip = ?', (ip,))
            existing_ip = await cursor.fetchone()
            if not existing_ip:
                # Добавляем новый IP с пустыми данными
                await db.execute('''
                    INSERT INTO ip_addresses (ip, ping, packet_loss, packet_received, last_successful_ping)
                    VALUES (?, ?, ?, ?, ?)
                ''', (ip, None, None, None, None))
        await db.commit()

    return {"message": "CSV imported successfully"}