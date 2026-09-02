from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import get_db
from main import app


# 使用独立的内存数据库，绝不读写正式 guild.db。
# StaticPool 让 TestClient 和测试代码共享同一个内存 SQLite 数据库。
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def create_category(db, name="讨伐", description="测试任务类别"):
    #以 QuestCategory建立实例 category 这整个函数用来返回一个category实例
    category = models.QuestCategory(name=name, description=description)
    db.add(category)
    #把这个 QuestCategory 对象插入它所映射的 quest_categories 表。
    #quest_categories 表 藏在models.QuestCategory定义里
    db.commit()
    db.refresh(category)
    return category

#这整个函数用来返回一个character实例，数据库填一行
def create_character(db, name="测试角色", race="人类", level=1):
    character = models.Character(
        name=name,
        race=race,
        level=level,
        country_id=1,
        real_country_id=1,
    )
    db.add(character)
    db.commit()
    db.refresh(character)
    return character
#为什么要return 养成习惯 新建对象习惯拿他的新id（refresh）
# 之前是（character_id = cursor.lastrowid）之类的 用于后续测试

def create_user(db,username = "testuser",
                #这些是默认值
                adventurer_name="测试冒险者",
                password_hash="test_password_hash",
                is_admin = False,
                adventurer_rank=models.AdventurerRank.COPPER,
                ):
    # 这个占位哈希只给不经过登录流程的业务测试使用。
    # 注册和登录测试必须走 /users/register，验证真实的 Argon2 哈希流程。
    user = models.User(
        username=username,
        adventurer_name=adventurer_name,
        password_hash=password_hash,
        is_admin=is_admin,
        adventurer_rank=adventurer_rank,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_party(db, name="测试小队"):
    party = models.Party(name=name)
    db.add(party)
    db.commit()
    db.refresh(party)
    return party


def create_quest(
    db,
    *,
    #* 后面的参数必须写名字，不能靠位置硬塞。这里参数太多 后面请求必须写清楚谁是谁
    title="测试任务",
    description="测试描述",
    completion_criteria="测试完成条件",
    category_id,
    status=models.QuestStatus.RECRUITING.value,
    minimum_rank=models.AdventurerRank.COPPER,
):
    quest = models.Quest(
        title=title,
        description=description,
        completion_criteria=completion_criteria,
        category_id=category_id,
        status=status,
        minimum_rank=minimum_rank,
    )
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest


def add_member(db, party_id, user_id, is_leader=False):
    member = models.PartyMember(
        party_id=party_id,
        user_id=user_id,
        is_leader=is_leader,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member
