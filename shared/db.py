# shared/db.py - 通用 SQLite helper（规则十一：三 Agent 共享基础设施）
# 从 Go购 src/db.py 提炼——各项目用自己的 DB_PATH，共用连接/初始化逻辑
import os
import sqlite3


def get_conn(db_path: str) -> sqlite3.Connection:
    """通用连接（项目自带 db_path）"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def execute(db_path: str, sql: str, args: tuple = ()) -> int:
    conn = get_conn(db_path)
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def query(db_path: str, sql: str, args: tuple = ()) -> list:
    conn = get_conn(db_path)
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()
