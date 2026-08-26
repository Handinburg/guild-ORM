from sqlalchemy import create_engine

from models import Base


DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"

engine = create_engine(DATABASE_URL, echo=True)

Base.metadata.create_all(engine)

print("数据表检查/创建完成")