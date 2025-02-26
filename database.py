from sqlite3 import connect, Row

def get_db():
    conn = connect('ip_addresses.db', check_same_thread=False)
    conn.row_factory = Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ip_addresses (
                ip TEXT PRIMARY KEY,
                ping REAL,
                packet_loss REAL,
                packet_received REAL,
                last_successful_ping TEXT
            )
        ''')