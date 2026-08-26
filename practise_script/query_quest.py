from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models import Quest


DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"

engine = create_engine(DATABASE_URL, echo=True)


with Session(engine) as db:
    statement = select(Quest)
    quests = db.scalars(statement).all()

    for quest in quests:
        print("任务ID：", quest.id)
        print("任务标题：", quest.title)
        print("类别ID：", quest.category_id)
        print("类别名称：", quest.category.name)
        print("任务状态：", quest.status)
        print("------")