# db.py
import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = "quantbot.db"

def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    c = _conn()
    cur = c.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        fees REAL DEFAULT 0.0,
        order_type TEXT,
        status TEXT,
        alpaca_order_id TEXT,
        note TEXT
    );
    CREATE TABLE IF NOT EXISTS positions (
        symbol TEXT PRIMARY KEY,
        qty INTEGER NOT NULL,
        avg_price REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS strategy_params (
        name TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    c.commit()
    c.close()

def persist_trade(symbol, side, qty, price, fees=0.0, order_type=None, status='filled', alpaca_order_id=None, note=None):
    c = _conn()
    cur = c.cursor()
    cur.execute("INSERT INTO trades (ts, symbol, side, qty, price, fees, order_type, status, alpaca_order_id, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), symbol, side, qty, price, fees, order_type, status, alpaca_order_id, note))
    c.commit()
    c.close()

def save_strategy_param(name, value):
    c = _conn()
    cur = c.cursor()
    cur.execute("INSERT INTO strategy_params (name, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (name, str(value), datetime.utcnow().isoformat()))
    c.commit()
    c.close()

def load_strategy_params():
    c = _conn()
    cur = c.cursor()
    cur.execute("SELECT name, value FROM strategy_params")
    rows = cur.fetchall()
    c.close()
    return {r[0]: r[1] for r in rows}

def get_trades(limit=200):
    c = _conn()
    cur = c.cursor()
    cur.execute("SELECT id, ts, symbol, side, qty, price, fees, order_type, status, alpaca_order_id, note FROM trades ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    c.close()
    return rows

