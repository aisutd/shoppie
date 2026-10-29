"""Read local MySQL settings and open one safe, caller-owned connection."""

import os


def read_config():
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError("Missing database settings: " + ", ".join(missing))
    try:
        port = int(os.environ.get("DB_PORT", "3306"))
    except ValueError:
        raise ValueError("DB_PORT must be an integer") from None
    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT must be between 1 and 65535")
    return {"host": os.environ["DB_HOST"], "port": port,
            "database": os.environ["DB_NAME"], "user": os.environ["DB_USER"],
            "password": os.environ["DB_PASSWORD"], "autocommit": False,
            "time_zone": "+00:00"}


def connect():
    config = read_config()
    try:
        import mysql.connector
    except ImportError:
        raise RuntimeError("Install mysql-connector-python for local MySQL ingestion") from None
    try:
        return mysql.connector.connect(**config)
    except mysql.connector.Error:
        raise RuntimeError("Could not connect to local MySQL; check DB settings and server") from None


def describe_connection(connection):
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute("SELECT DATABASE(), VERSION()")
        database, version = cursor.fetchone()
        return {"database": database, "version": version}
    finally:
        cursor.close()
