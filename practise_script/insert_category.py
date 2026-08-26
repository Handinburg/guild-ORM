from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import QuestCategory


DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/guild-ORM/guild.db"

engine = create_engine(DATABASE_URL, echo=True)


with Session(engine) as db:
    category = QuestCategory(
        name="讨伐",
        description="消灭指定的怪物",
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    print("新增成功：")
    print(category.id, category.name, category.description)