"""MySQL connection helpers."""

from collections.abc import Iterator
from contextlib import contextmanager

import mysql.connector
from mysql.connector import MySQLConnection

from echolens.core.config import Settings, get_settings


@contextmanager
def mysql_connection(settings: Settings | None = None) -> Iterator[MySQLConnection]:
    """Open a MySQL connection and close it after use."""

    runtime_settings = settings or get_settings()
    connection = mysql.connector.connect(
        host=runtime_settings.mysql_host,
        port=runtime_settings.mysql_port,
        user=runtime_settings.mysql_user,
        password=runtime_settings.mysql_password,
        database=runtime_settings.mysql_database,
    )
    try:
        yield connection
    finally:
        connection.close()
