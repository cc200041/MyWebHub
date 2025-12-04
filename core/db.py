# 文件: core/db.py
import sqlite3
import config

def get_diet_conn():
    conn = sqlite3.connect(config.DB_DIET)
    conn.row_factory = sqlite3.Row
    return conn

def get_cook_conn():
    conn = sqlite3.connect(config.DB_COOK)
    conn.row_factory = sqlite3.Row
    return conn
