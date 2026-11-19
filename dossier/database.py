from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry


def create_database_engine(database_url: str) -> Engine:
    engine = create_engine(
        database_url, connect_args={"timeout": 5, "isolation_level": "IMMEDIATE", "check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def set_pragmas(dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine
