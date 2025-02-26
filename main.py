from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pythonping import ping as python_ping
from datetime import datetime
from database import get_db, init_db
from models import IPInfo
import sqlite3
import asyncio
import threading
import csv
import io
import re

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
init_db()

# Отдача статических файлов (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# Маршрут для главной страницы
@app.get("/")
def serve_frontend():
    return FileResponse("frontend/index.html")


# WebSocket для обновления данных в реальном времени
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")  # Логирование
    try:
        while True:
            ips = get_all_ips()
            print("Sending data:", ips)  # Логирование
            await websocket.send_json(jsonable_encoder(ips))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("WebSocket disconnected")


# Функция для пингования IP-адреса
def ping_ip(ip: str):
    try:
        # Используем pythonping для пингования
        response = python_ping(ip, count=4, timeout=1)
        print(f"Ping response for {ip}: {response}")  # Логирование

        # Подсчет успешных пингов
        success_count = sum(1 for r in response if r.success)
        packet_loss = 100 - (success_count / 4) * 100  # Процент потерянных пакетов
        packet_received = 100 - packet_loss  # Процент полученных пакетов
        avg_ping = response.rtt_avg_ms  # Средний пинг
        last_successful_ping = datetime.now() if success_count > 0 else None

    except Exception as e:
        print(f"Error pinging {ip}: {e}")
        packet_loss = 100
        packet_received = 0
        avg_ping = None
        last_successful_ping = None

    db = get_db()
    with db:
        db.execute('''
            UPDATE ip_addresses
            SET ping = ?, packet_loss = ?, packet_received = ?, last_successful_ping = ?
            WHERE ip = ?
        ''', (avg_ping, packet_loss, packet_received, last_successful_ping, ip))


# Функция для периодического пингования всех IP-адресов
def start_pinging():
    while True:
        db = get_db()
        with db:
            ips = db.execute('SELECT ip FROM ip_addresses').fetchall()
        for ip in ips:
            ping_ip(ip['ip'])
        asyncio.sleep(10)  # Пинговать каждые 10 секунд


# Запуск потока для пингования
threading.Thread(target=start_pinging, daemon=True).start()


# Остальные маршруты
@app.post("/ip/", response_model=IPInfo)
def add_ip(ip_info: IPInfo):
    if not validate_ip(ip_info.ip):
        raise HTTPException(status_code=400, detail="Invalid IP address format")

    db = get_db()
    with db:
        db.execute('''
            INSERT OR REPLACE INTO ip_addresses (ip, ping, packet_loss, packet_received, last_successful_ping)
            VALUES (?, ?, ?, ?, ?)
        ''', (ip_info.ip, ip_info.ping, ip_info.packet_loss, ip_info.packet_received, ip_info.last_successful_ping))
    return ip_info


@app.get("/ip/{ip}", response_model=IPInfo)
def get_ip(ip: str):
    db = get_db()
    with db:
        row = db.execute('SELECT * FROM ip_addresses WHERE ip = ?', (ip,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="IP not found")
    return IPInfo(**row)


@app.delete("/ip/{ip}")
def delete_ip(ip: str):
    db = get_db()
    with db:
        db.execute('DELETE FROM ip_addresses WHERE ip = ?', (ip,))
    return {"message": "IP deleted"}


@app.put("/ip/{old_ip}", response_model=IPInfo)
def edit_ip(old_ip: str, new_ip_info: IPInfo):
    if not validate_ip(new_ip_info.ip):
        raise HTTPException(status_code=400, detail="Invalid IP address format")

    db = get_db()
    with db:
        # Проверяем, существует ли старый IP
        row = db.execute('SELECT * FROM ip_addresses WHERE ip = ?', (old_ip,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Old IP not found")

        # Обновляем IP
        db.execute('''
            UPDATE ip_addresses
            SET ip = ?, ping = ?, packet_loss = ?, packet_received = ?, last_successful_ping = ?
            WHERE ip = ?
        ''', (new_ip_info.ip, new_ip_info.ping, new_ip_info.packet_loss, new_ip_info.packet_received,
              new_ip_info.last_successful_ping, old_ip))
    return new_ip_info


@app.get("/ip/")
def get_all_ips():
    db = get_db()
    with db:
        rows = db.execute('SELECT * FROM ip_addresses').fetchall()
    ips = [IPInfo(**row).dict() for row in rows]
    print("IPs from database:", ips)  # Логирование
    return ips


# Экспорт данных в CSV
@app.get("/export-csv/")
def export_csv():
    db = get_db()
    with db:
        rows = db.execute('SELECT * FROM ip_addresses').fetchall()

    # Создаем CSV-файл в памяти
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["IP", "Ping (ms)", "Packet Loss (%)", "Packet Received (%)", "Last Successful Ping"])  # Заголовки
    for row in rows:
        writer.writerow(
            [row['ip'], row['ping'], row['packet_loss'], row['packet_received'], row['last_successful_ping']])

    # Возвращаем CSV-файл как ответ
    output.seek(0)
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=ip_addresses.csv"})


# Импорт данных из CSV (только IP-адреса)
@app.post("/import-csv/")
async def import_csv(file: UploadFile = File(...)):
    db = get_db()
    content = await file.read()
    content = content.decode("utf-8").splitlines()
    reader = csv.reader(content)

    with db:
        for row in reader:
            ip = row[0]  # Берем только первый столбец (IP-адрес)
            if not validate_ip(ip):
                print(f"Skipping invalid IP: {ip}")
                continue  # Пропускаем невалидные IP-адреса

            # Проверяем, существует ли уже такой IP в базе
            existing_ip = db.execute('SELECT ip FROM ip_addresses WHERE ip = ?', (ip,)).fetchone()
            if not existing_ip:
                # Добавляем новый IP с пустыми данными
                db.execute('''
                    INSERT INTO ip_addresses (ip, ping, packet_loss, packet_received, last_successful_ping)
                    VALUES (?, ?, ?, ?, ?)
                ''', (ip, None, None, None, None))

    return {"message": "CSV imported successfully"}