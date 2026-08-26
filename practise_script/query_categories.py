from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models import QuestCategory


DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"

engine = create_engine(DATABASE_URL, echo=True)


with Session(engine) as db:
    statement = select(QuestCategory)
    categories = db.scalars(statement).all()

    print("任务类别数量：", len(categories))

    for category in categories:
        print(
            category.id,
            category.name,
            category.description,
        )