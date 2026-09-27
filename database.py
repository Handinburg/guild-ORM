from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from pathlib import Path

#以代码文件的位置为参照，找到旁边的数据库文件。 
# Path创建path对象，resolve看绝对路径 .parent看上一级
#拿到当前 Python 文件所在的目录。
PROJECT_DIR = Path(__file__).resolve().parent

#在这个目录后面拼上数据库文件名。
DATABASE_PATH = PROJECT_DIR / "guild_alembic_v1.db"

#.as_posix()：把路径对象转换为用 / 分隔的字符串。
#加上 sqlite:///：告诉 SQLAlchemy 用 SQLite 打开这个文件。
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

#老的绝对路径
#DATABASE_URL =  ("sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild_alembic_v1.db")




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
