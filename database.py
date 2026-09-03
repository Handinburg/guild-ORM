from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DATABASE_URL =  (
    "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"
)
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread":False
    }
)


def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


event.listen(engine, "connect", enable_sqlite_foreign_keys)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
