from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Quest


DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"

engine = create_engine(DATABASE_URL, echo=True)


with Session(engine) as db:
    quest = Quest(
        title="清除森林史莱姆",
        description="森林附近出现了大量史莱姆，请冒险者前往处理。",
        completion_criteria="消灭10只史莱姆",
        category_id=1,
    )

    db.add(quest)
    db.commit()
    db.refresh(quest)

    print("任务创建成功：")
    print("ID：", quest.id)
    print("标题：", quest.title)
    print("状态：", quest.status)
    print("类别ID：", quest.category_id)