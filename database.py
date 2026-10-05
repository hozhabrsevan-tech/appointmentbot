
import sqlite3
from datetime import date

DB_NAME = "appointment.db"


def connect_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        full_name TEXT NOT NULL,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        role TEXT NOT NULL DEFAULT 'operator'
    );

    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        duration INTEGER NOT NULL,
        price INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS time_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_id INTEGER NOT NULL,
        slot_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        is_available INTEGER DEFAULT 1,
        FOREIGN KEY (service_id) REFERENCES services(id),
        UNIQUE (slot_date, start_time)
    );

    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service_id INTEGER NOT NULL,
        slot_id INTEGER NOT NULL UNIQUE,
        customer_name TEXT NOT NULL,
        customer_phone TEXT,
        status TEXT DEFAULT 'confirmed',
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (service_id) REFERENCES services(id),
        FOREIGN KEY (slot_id) REFERENCES time_slots(id),
        FOREIGN KEY (created_by) REFERENCES admins(id)
    );

    CREATE TABLE IF NOT EXISTS holidays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        holiday_date TEXT NOT NULL UNIQUE,
        description TEXT
    );
    """)

    conn.commit()
    conn.close()


def add_admin(telegram_id):
    conn = connect_db()
    conn.execute(
        "INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)",
        (telegram_id,)
    )
    conn.commit()
    conn.close()


def get_admin_db_id(telegram_id):
    conn = connect_db()
    row = conn.execute(
        "SELECT id FROM admins WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def add_user(telegram_id, full_name, phone=None):
    conn = connect_db()
    conn.execute("""
        INSERT INTO users (telegram_id, full_name, phone)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            full_name = excluded.full_name
    """, (telegram_id, full_name, phone))
    conn.commit()
    conn.close()


def get_user_id(telegram_id):
    conn = connect_db()
    row = conn.execute(
        "SELECT id FROM users WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def add_service(name, description, duration, price):
    conn = connect_db()
    conn.execute("""
        INSERT INTO services (name, description, duration, price)
        VALUES (?, ?, ?, ?)
    """, (name, description, duration, price))
    conn.commit()
    conn.close()


def get_services():
    conn = connect_db()
    rows = conn.execute("""
        SELECT * FROM services
        WHERE is_active = 1
        ORDER BY id
    """).fetchall()
    conn.close()
    return rows


def add_time_slot(service_id, slot_date, start_time, end_time):
    conn = connect_db()
    conn.execute("""
        INSERT INTO time_slots
        (service_id, slot_date, start_time, end_time)
        VALUES (?, ?, ?, ?)
    """, (service_id, slot_date, start_time, end_time))
    conn.commit()
    conn.close()


def get_available_dates(service_id):
    conn = connect_db()
    rows = conn.execute("""
        SELECT DISTINCT slot_date
        FROM time_slots
        WHERE service_id = ?
          AND is_available = 1
          AND slot_date >= ?
          AND slot_date NOT IN (
              SELECT holiday_date FROM holidays
          )
        ORDER BY slot_date
    """, (service_id, date.today().isoformat())).fetchall()
    conn.close()
    return rows


def get_available_slots(service_id, slot_date):
    conn = connect_db()
    rows = conn.execute("""
        SELECT * FROM time_slots
        WHERE service_id = ?
          AND slot_date = ?
          AND is_available = 1
        ORDER BY start_time
    """, (service_id, slot_date)).fetchall()
    conn.close()
    return rows


def book_appointment(
    telegram_id, service_id, slot_id, customer_name
):
    conn = connect_db()
    try:
        conn.execute("BEGIN IMMEDIATE")

        user = conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?",
            (telegram_id,)
        ).fetchone()

        if user is None:
            conn.rollback()
            return False

        slot = conn.execute("""
            SELECT slot_date
            FROM time_slots
            WHERE id = ?
              AND service_id = ?
              AND is_available = 1
        """, (slot_id, service_id)).fetchone()

        if slot is None:
            conn.rollback()
            return False

        holiday = conn.execute(
            "SELECT id FROM holidays WHERE holiday_date = ?",
            (slot["slot_date"],)
        ).fetchone()

        if holiday:
            conn.rollback()
            return False

        changed = conn.execute("""
            UPDATE time_slots
            SET is_available = 0
            WHERE id = ? AND is_available = 1
        """, (slot_id,))

        if changed.rowcount != 1:
            conn.rollback()
            return False

        conn.execute("""
            INSERT INTO appointments (
                user_id, service_id, slot_id, customer_name
            )
            VALUES (?, ?, ?, ?)
        """, (user["id"], service_id, slot_id, customer_name))

        conn.commit()
        return True

    except sqlite3.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_user_appointments(telegram_id):
    conn = connect_db()
    rows = conn.execute("""
        SELECT
            a.id, a.customer_name, s.name AS service_name,
            t.slot_date, t.start_time, t.end_time
        FROM appointments a
        JOIN users u ON a.user_id = u.id
        JOIN services s ON a.service_id = s.id
        JOIN time_slots t ON a.slot_id = t.id
        WHERE u.telegram_id = ?
          AND a.status = 'confirmed'
        ORDER BY t.slot_date, t.start_time
    """, (telegram_id,)).fetchall()
    conn.close()
    return rows


def get_all_appointments():
    conn = connect_db()
    rows = conn.execute("""
        SELECT
            a.id, a.customer_name, a.customer_phone,
            s.name AS service_name,
            t.slot_date, t.start_time, t.end_time,
            a.status
        FROM appointments a
        JOIN services s ON a.service_id = s.id
        JOIN time_slots t ON a.slot_id = t.id
        ORDER BY t.slot_date, t.start_time
    """).fetchall()
    conn.close()
    return rows


def cancel_appointment(appointment_id, telegram_id=None):
    conn = connect_db()
    try:
        conn.execute("BEGIN IMMEDIATE")

        if telegram_id is None:
            row = conn.execute("""
                SELECT slot_id FROM appointments
                WHERE id = ? AND status = 'confirmed'
            """, (appointment_id,)).fetchone()
        else:
            row = conn.execute("""
                SELECT a.slot_id
                FROM appointments a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = ?
                  AND u.telegram_id = ?
                  AND a.status = 'confirmed'
            """, (appointment_id, telegram_id)).fetchone()

        if row is None:
            conn.rollback()
            return False

        conn.execute("""
            UPDATE appointments
            SET status = 'cancelled'
            WHERE id = ?
        """, (appointment_id,))

        conn.execute("""
            UPDATE time_slots
            SET is_available = 1
            WHERE id = ?
        """, (row["slot_id"],))

        conn.commit()
        return True
    finally:
        conn.close()





