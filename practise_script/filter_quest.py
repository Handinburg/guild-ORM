from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models import Quest, QuestStatus


DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"

engine = create_engine(DATABASE_URL, echo=True)


with Session(engine) as db:
    statement = (
        select(Quest)
        .where(Quest.status == QuestStatus.RECRUITING.value,
                Quest.category.has(name="讨伐")
                )
        .order_by(Quest.id.desc())
        .offset(0)
        .limit(10)
    )

    quests = db.scalars(statement).all()

    for quest in quests:
        print(
            quest.id,
            quest.title,
            quest.status,
            quest.category.name,
        )
