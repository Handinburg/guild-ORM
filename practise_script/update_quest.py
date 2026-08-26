from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Quest


DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"

engine = create_engine(DATABASE_URL, echo=True)


with Session(engine) as db:
    quest = db.get(Quest, 1)

    if quest is None:
        print("任务不存在")
    else:
        print("修改前：", quest.completion_criteria)

        quest.completion_criteria = "消灭10只史莱姆，并带回3个史莱姆核心"

        db.commit()
        db.refresh(quest)

        print("修改后：", quest.completion_criteria)