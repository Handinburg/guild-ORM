from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Quest


DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"

engine = create_engine(DATABASE_URL, echo=True)


with Session(engine) as db:
    temporary_quest = Quest(
        title="临时测试任务",
        description="用于练习删除",
        completion_criteria="无",
        category_id=1,
    )

    db.add(temporary_quest)
    db.commit()
    db.refresh(temporary_quest)

    print("临时任务已创建，ID：", temporary_quest.id)

    db.delete(temporary_quest)
    db.commit()

    print("临时任务已删除")