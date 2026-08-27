from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

import models
from database import get_db
from main import app
from security import verify_password


# 使用内存数据库，避免读写正式 guild.db
# 通过 StaticPool 保证每次测试都使用同一个内存 SQLite 连接。
test_engine = create_engine(
    "sqlite://",
    connect_args={
        "check_same_thread": False,
    },
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


# 每个测试开始前都清空数据库，确保测试独立且不依赖顺序
# 这与项目要求一致：只能操作测试数据库，不触碰正式 guild.db

def setup_function():
    #所有base基类下的表 都删掉重新创建 handle用我们的test_engine
    models.Base.metadata.drop_all(bind=test_engine)
    models.Base.metadata.create_all(bind=test_engine)


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

def create_user(db,username = "testuser123",
                adventurer_name="test_adventurer_name",
                password_hash="test_password_hash",
                ):
    user = models.User(
        username=username,
        adventurer_name=adventurer_name,
        password_hash=password_hash,
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
    status="open",
    is_cooperative=False,
):
    quest = models.Quest(
        title=title,
        description=description,
        completion_criteria=completion_criteria,
        category_id=category_id,
        status=status,
        is_cooperative=is_cooperative,
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


# 一、小队功能

def test_get_missing_party_returns_404():
    response = client.get("/parties/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "小队不存在"}


def test_create_party_returns_201_and_checks_data():
    response = client.post(
        "/parties",
        json={"name": "自动测试小队"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "自动测试小队"
    assert data["member_list"] == []


def test_create_duplicate_party_returns_409():
#先给db里加一条 100%成功 不需返回201
    db = TestSessionLocal()
    create_party(db, name="银丝鸟")
    db.close()
#在真正测试我们想要的409
    response = client.post(
        "/parties",
        json={"name": "银丝鸟"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "小队名称已存在"}


def test_get_party_returns_members():
    db = TestSessionLocal()
    party = create_party(db, name="成员小队")
    user = create_user(db, username="角色A")
    add_member(db, party.id, user.id, is_leader=True)
    party_id = party.id
    user_id = user.id
    db.close()

    response = client.get(f"/parties/{party_id}")
#之前定义路由时不需要 f-string，
# 因为那时不是在填值，而是在声明一个“等待填空的位置”
#现在是在填值了
    assert response.status_code == 200
    data = response.json()

#response.json()  # 把收到的JSON拆成Python数据
#json={...}       # 把Python数据包装成JSON发出去
    assert data["id"] == party_id
    assert data["name"] == "成员小队"
    assert len(data["member_list"]) == 1
    assert data["member_list"][0]["user_id"] == user_id
    assert data["member_list"][0]["is_leader"] is True


def test_delete_party_success():
    db = TestSessionLocal()
    party = create_party(db, name="待删除小队")
    party_id = party.id
    db.close()

    response = client.delete(f"/parties/{party_id}")

    assert response.status_code == 204
    assert response.content == b""
#表示一个空的 bytes，也就是零字节：什么都没有返回
#你必须没有偷偷返回 JSON 或其他内容。
    check_response = client.get(f"/parties/{party_id}")
    assert check_response.status_code == 404
    assert check_response.json() == {"detail": "小队不存在"}


def test_delete_missing_party_returns_404():
    response = client.delete("/parties/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "小队不存在"}


# 二、小队成员功能

def test_add_member_to_existing_party():
    db = TestSessionLocal()
    party = create_party(db, name="战队")
    user = create_user(db, username="勇者")
    party_id = party.id
    user_id = user.id
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={"user_id": user_id, "is_leader": True},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["party_id"] == party_id
    assert data["user_id"] == user_id
    assert data["is_leader"] is True
    assert data["user"]["username"] == "勇者"
    assert "character_id" not in data
    assert "character" not in data

    db = TestSessionLocal()
    stored_member = db.scalar(
        select(models.PartyMember).where(
            models.PartyMember.user_id == user_id
        )
    )
    assert stored_member is not None
    assert stored_member.party_id == party_id
    db.close()


def test_add_member_to_missing_party_returns_404():
    response = client.post(
        "/parties/999999/members",
        json={"user_id": 1, "is_leader": False},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "小队不存在"}


def test_add_missing_user_to_party_returns_404():
    db = TestSessionLocal()
    party = create_party(db, name="缺人小队")
    party_id = party.id
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={"user_id": 999999, "is_leader": False},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "用户不存在"}


def test_add_member_rejects_old_character_id_field():
    db = TestSessionLocal()
    party = create_party(db, name="旧字段小队")
    character = create_character(db, name="独立角色")
    party_id = party.id
    character_id = character.id
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={"character_id": character_id},
    )

    assert response.status_code == 422
    db = TestSessionLocal()
    assert db.scalar(select(models.PartyMember)) is None
    assert db.get(models.Character, character_id) is not None
    db.close()


def test_add_duplicate_member_returns_409():
    db = TestSessionLocal()
    party = create_party(db, name="重复小队")
    user = create_user(db, username="重复角色")
    add_member(db, party.id, user.id, is_leader=False)
    party_id = party.id
    user_id = user.id
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={"user_id": user_id, "is_leader": False},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "该用户已经加入小队"}

    db = TestSessionLocal()
    members = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.user_id == user_id
        )
    ).all()
    assert len(members) == 1
    assert members[0].party_id == party_id
    db.close()


def test_user_cannot_join_two_parties():
    db = TestSessionLocal()
    first_party = create_party(db, name="第一小队")
    second_party = create_party(db, name="第二小队")
    user = create_user(db, username="只能入一队")
    add_member(db, first_party.id, user.id)
    first_party_id = first_party.id
    second_party_id = second_party.id
    user_id = user.id
    db.close()

    response = client.post(
        f"/parties/{second_party_id}/members",
        json={"user_id": user_id},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "该用户已经加入小队"}
    db = TestSessionLocal()
    members = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.user_id == user_id
        )
    ).all()
    assert len(members) == 1
    assert members[0].party_id == first_party_id
    db.close()


def test_remove_member_success():
    db = TestSessionLocal()
    party = create_party(db, name="离队小队")
    user = create_user(db, username="离队角色")
    add_member(db, party.id, user.id, is_leader=False)
    party_id = party.id
    user_id = user.id
    db.close()

    response = client.delete(f"/parties/{party_id}/members/{user_id}")

    assert response.status_code == 204
    assert response.content == b""

    check_response = client.get(f"/parties/{party_id}")
    assert check_response.status_code == 200
    assert all(item["user_id"] != user_id for item in check_response.json()["member_list"])


def test_remove_missing_member_returns_404():
    db = TestSessionLocal()
    party = create_party(db, name="空小队")
    party_id = party.id
    db.close()

    response = client.delete(f"/parties/{party_id}/members/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "该用户不在此小队中"}


def test_change_leader_success():
    db = TestSessionLocal()
    party = create_party(db, name="换队长小队")
    old_leader = create_user(db, username="旧队长")
    new_leader = create_user(db, username="新队长")
    add_member(db, party.id, old_leader.id, is_leader=True)
    add_member(db, party.id, new_leader.id, is_leader=False)
    party_id = party.id
    new_leader_id = new_leader.id
    db.close()

    response = client.patch(
        f"/parties/{party_id}/leader",
        json={"user_id": new_leader_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == party_id
    assert [member["user_id"] for member in data["member_list"] if member["is_leader"]] == [new_leader_id]

    db = TestSessionLocal()
    stored_members = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.party_id == party_id
        )
    ).all()
    assert [member.user_id for member in stored_members if member.is_leader] == [new_leader_id]
    db.close()


def test_change_leader_to_non_member_returns_404():
    db = TestSessionLocal()
    party = create_party(db, name="非成员队长")
    old_leader = create_user(db, username="当前队长")
    add_member(db, party.id, old_leader.id, is_leader=True)
    outsider = create_user(db, username="外部角色")
    party_id = party.id
    outsider_id = outsider.id
    db.close()

    response = client.patch(
        f"/parties/{party_id}/leader",
        json={"user_id": outsider_id},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "新队长不是该小队成员"}


def test_change_leader_to_same_current_leader_returns_409():
    db = TestSessionLocal()
    party = create_party(db, name="重复队长")
    leader = create_user(db, username="队长本人")
    add_member(db, party.id, leader.id, is_leader=True)
    party_id = party.id
    leader_id = leader.id
    db.close()

    response = client.patch(
        f"/parties/{party_id}/leader",
        json={"user_id": leader_id},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "无效修改,此人已是队长"}


# 三、任务功能

def test_create_quest_returns_201():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    category_id = category.id
    db.close()

    response = client.post(
        "/quests",
        json={
            "title": "讨伐哥布林",
            "description": "村庄附近出现了哥布林",
            "completion_criteria": "消灭5只哥布林",
            "category_id": category_id,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "讨伐哥布林"
    assert data["category_id"] == category_id
    assert data["status"] == "open"


def test_create_quest_with_missing_category_returns_404():
    response = client.post(
        "/quests",
        json={
            "title": "讨伐哥布林",
            "description": "村庄附近出现了哥布林",
            "completion_criteria": "消灭5只哥布林",
            "category_id": 999999,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "任务类别不存在"}


def test_get_existing_quest():
    db = TestSessionLocal()
    category = create_category(db, name="采集")
    quest = create_quest(db, title="采集蘑菇", category_id=category.id)
    quest_id = quest.id
    category_id = category.id
    db.close()

    response = client.get(f"/quests/{quest_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == quest_id
    assert data["title"] == "采集蘑菇"
    assert data["category_id"] == category_id


def test_get_missing_quest_returns_404():
    response = client.get("/quests/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "任务不存在"}


def test_update_quest():
    db = TestSessionLocal()
    category = create_category(db, name="护送")
    new_category = create_category(db, name="调查")
    quest = create_quest(db, title="护送商队", category_id=category.id)
    quest_id = quest.id
    new_category_id = new_category.id
    db.close()

    response = client.patch(
        f"/quests/{quest_id}",
        json={
            "title": "调查遗迹",
            "description": "前往遗迹探索",
            "completion_criteria": "找到地图碎片",
            "category_id": new_category_id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "调查遗迹"
    assert data["description"] == "前往遗迹探索"
    assert data["completion_criteria"] == "找到地图碎片"
    assert data["category_id"] == new_category_id


def test_delete_quest():
    db = TestSessionLocal()
    category = create_category(db, name="清理")
    quest = create_quest(db, title="清理洞穴", category_id=category.id)
    quest_id = quest.id
    db.close()

    response = client.delete(f"/quests/{quest_id}")

    assert response.status_code == 204
    assert response.content == b""

    check_response = client.get(f"/quests/{quest_id}")
    assert check_response.status_code == 404
    assert check_response.json() == {"detail": "任务不存在"}


def test_filter_quests_by_status():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    create_quest(db, title="A", category_id=category.id, status="open")
    create_quest(db, title="B", category_id=category.id, status="commenced")
    create_quest(db, title="C", category_id=category.id, status="commenced")
    db.close()

    response = client.get("/quests", params={"status": "commenced"})
#GET筛选用 params= POST、PUT、PATCH填表用 json= ID放进网址{}

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {item["title"] for item in data} == {"B", "C"}


def test_filter_quests_by_category_name():
    db = TestSessionLocal()
    category_a = create_category(db, name="讨伐")
    category_b = create_category(db, name="采集")
    create_quest(db, title="讨伐怪物", category_id=category_a.id)
    create_quest(db, title="采集草药", category_id=category_b.id)
    create_quest(db, title="再次讨伐", category_id=category_a.id)
    db.close()

    response = client.get("/quests", params={"category_name": "讨伐"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {item["title"] for item in data} == {"讨伐怪物", "再次讨伐"}


def test_update_quest_status_manually():
    db = TestSessionLocal()
    category = create_category(db, name="调查")
    quest = create_quest(db, title="调查遗迹", category_id=category.id, status="open")
    quest_id = quest.id
    db.close()

    response = client.patch(
        f"/quests/{quest_id}/status",
        json={"status": "finished"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "finished"


def test_update_quest_status_invalid_returns_400():
    db = TestSessionLocal()
    category = create_category(db, name="护送")
    quest = create_quest(db, title="护送老人", category_id=category.id, status="open")
    quest_id = quest.id
    db.close()

    response = client.patch(
        f"/quests/{quest_id}/status",
        json={"status": "not_real"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["请重新规范输入status 参考管理员手册"]}


# 四、小队参与任务功能

def test_party_accepts_quest():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(db, title="低级任务", category_id=category.id, status="open")
    party = create_party(db, name="接任务小队")
    quest_id = quest.id
    party_id = party.id
    db.close()

    response = client.post(f"/parties/{party_id}/quests/{quest_id}")

    assert response.status_code == 201
    data = response.json()
    assert data["party_id"] == party_id
    assert data["quest_id"] == quest_id

    quest_response = client.get(f"/quests/{quest_id}")
    assert quest_response.status_code == 200
    assert quest_response.json()["status"] == "commenced"


def test_accept_quest_missing_party_returns_404():
    db = TestSessionLocal()
    category = create_category(db, name="护送")
    quest = create_quest(db, title="护送木车", category_id=category.id, status="open")
    quest_id = quest.id
    db.close()

    response = client.post(f"/parties/99999/quests/{quest_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "小队不存在"}


def test_accept_quest_missing_quest_returns_404():
    db = TestSessionLocal()
    party = create_party(db, name="空任务队")
    party_id = party.id
    db.close()

    response = client.post(f"/parties/{party_id}/quests/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "任务不存在"}


def test_same_party_cannot_accept_same_quest_twice():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(db, title="重复接取", category_id=category.id, status="open")
    party = create_party(db, name="重复接取队")
    party_id = party.id
    quest_id = quest.id
    db.close()

    first = client.post(f"/parties/{party_id}/quests/{quest_id}")
    second = client.post(f"/parties/{party_id}/quests/{quest_id}")

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "该小队已经接受过此任务"}


def test_non_cooperative_quest_cannot_be_accepted_by_second_party_returns_409():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(db, title="独占任务", category_id=category.id, status="open")
    party_a = create_party(db, name="A队")
    party_b = create_party(db, name="B队")
    party_a_id = party_a.id
    party_b_id = party_b.id
    quest_id = quest.id
    db.close()

    first = client.post(f"/parties/{party_a_id}/quests/{quest_id}")
    second = client.post(f"/parties/{party_b_id}/quests/{quest_id}")

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "该任务已经被其他小队接受"}


def test_cooperative_quest_allows_multiple_parties():
    db = TestSessionLocal()
    category = create_category(db, name="合作")
    quest = create_quest(db, title="团队副本", category_id=category.id, status="open", is_cooperative=True)
    party_a = create_party(db, name="合作队A")
    party_b = create_party(db, name="合作队B")
    party_a_id = party_a.id
    party_b_id = party_b.id
    quest_id = quest.id
    db.close()

    response_a = client.post(f"/parties/{party_a_id}/quests/{quest_id}")
    response_b = client.post(f"/parties/{party_b_id}/quests/{quest_id}")

    assert response_a.status_code == 201
    assert response_b.status_code == 201

    quest_response = client.get(f"/quests/{quest_id}")
    assert quest_response.status_code == 200
    assert quest_response.json()["status"] == "open"


def test_get_party_quests():
    db = TestSessionLocal()
    category = create_category(db, name="调查")
    quest_a = create_quest(db, title="任务A", category_id=category.id, status="open")
    quest_b = create_quest(db, title="任务B", category_id=category.id, status="open")
    party = create_party(db, name="查询任务队")
    party_id = party.id
    quest_a_id = quest_a.id
    quest_b_id = quest_b.id
    db.close()

    client.post(f"/parties/{party_id}/quests/{quest_a_id}")
    client.post(f"/parties/{party_id}/quests/{quest_b_id}")

    response = client.get(f"/parties/{party_id}/quests")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {item["title"] for item in data} == {"任务A", "任务B"}


def test_get_quest_parties():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(
        db,
        title="集结讨伐",
        category_id=category.id,
        status="open",
        is_cooperative=True,
    )
    party_a = create_party(db, name="P1")
    party_b = create_party(db, name="P2")
    party_a_id = party_a.id
    party_b_id = party_b.id
    quest_id = quest.id
    db.close()

    client.post(f"/parties/{party_a_id}/quests/{quest_id}")
    client.post(f"/parties/{party_b_id}/quests/{quest_id}")

    response = client.get(f"/quests/{quest_id}/parties")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {item["name"] for item in data} == {"P1", "P2"}


def test_withdraw_from_quest():
    db = TestSessionLocal()
    category = create_category(db, name="采集")
    quest = create_quest(db, title="采集药材", category_id=category.id, status="open")
    party = create_party(db, name="退出队")
    quest_id = quest.id
    party_id = party.id
    db.close()

    client.post(f"/parties/{party_id}/quests/{quest_id}")

    response = client.delete(f"/parties/{party_id}/quests/{quest_id}")

    assert response.status_code == 204
    assert response.content == b""

    check_response = client.get(f"/quests/{quest_id}")
    assert check_response.status_code == 200
    assert check_response.json()["status"] == "open"


def test_withdraw_missing_participation_returns_404():
    db = TestSessionLocal()
    category = create_category(db, name="采集")
    quest = create_quest(db, title="无参与任务", category_id=category.id, status="open")
    party = create_party(db, name="没参与队")
    quest_id = quest.id
    party_id = party.id
    db.close()

    response = client.delete(f"/parties/{party_id}/quests/{quest_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "该小队没有参与此任务"}


def test_last_party_withdraw_reopens_quest():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(db, title="最终任务", category_id=category.id, status="open")
    party = create_party(db, name="最后一个队")
    party_id = party.id
    quest_id = quest.id
    db.close()

    client.post(f"/parties/{party_id}/quests/{quest_id}")
    response = client.delete(f"/parties/{party_id}/quests/{quest_id}")

    assert response.status_code == 204
    check_response = client.get(f"/quests/{quest_id}")
    assert check_response.status_code == 200
    assert check_response.json()["status"] == "open"

def test_register_user_201():
    response = client.post(
        "/users/register",
        json={
            "username": "test_wild_rat",
            "adventurer_name": "测试吱吱",
            "password": "guild12345",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["username"] == "test_wild_rat"
    assert data["adventurer_name"] == "测试吱吱"
    assert data["is_admin"] is False

    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data

    db = TestSessionLocal()
    stored_user = db.scalar(
        select(models.User).where(
            models.User.username == "test_wild_rat"
        )
    )
    assert stored_user is not None
    assert stored_user.password_hash != "guild12345"
    assert verify_password("guild12345", stored_user.password_hash)
    assert stored_user.is_admin is False
    db.close()


def test_register_cannot_grant_admin_or_expose_password():
    response = client.post(
        "/users/register",
        json={
            "username": "not_an_admin",
            "adventurer_name": "普通冒险者",
            "password": "guild12345",
            "is_admin": True,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["is_admin"] is False
    assert "password" not in data
    assert "password_hash" not in data

    db = TestSessionLocal()
    stored_user = db.scalar(
        select(models.User).where(
            models.User.username == "not_an_admin"
        )
    )
    assert stored_user is not None
    assert stored_user.is_admin is False
    db.close()

def test_register_duplicate_username_409():
    user_data = {
        "username": "duplicate_rat",
        "adventurer_name": "重复鼠",
        "password": "guild12345",
    }

    first_response = client.post(
        "/users/register",
        json=user_data,
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/users/register",
        json=user_data,
    )

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "用户名已存在"
    }



# 完整的业务流程测试

def test_full_business_flow():
    db = TestSessionLocal()
    category = create_category(db, name="护送")
    user = create_user(db, username="主角")
    party = create_party(db, name="护送队")
    add_member(db, party.id, user.id, is_leader=True)
    quest = create_quest(
        db,
        title="护送商队",
        description="护送商人穿过森林",
        completion_criteria="安全到达村落",
        category_id=category.id,
        status="open",
    )
    party_id = party.id
    quest_id = quest.id
    db.close()

    accept_response = client.post(f"/parties/{party_id}/quests/{quest_id}")
    assert accept_response.status_code == 201

    party_quests = client.get(f"/parties/{party_id}/quests")
    assert party_quests.status_code == 200
    assert any(item["id"] == quest_id for item in party_quests.json())
    #返回的任务列表中，只要有一个任务的 ID 等于刚才那个任务 ID，就通过。
    update_status_response = client.patch(
        f"/quests/{quest_id}/status",
        json={"status": "finished"},
    )
    assert update_status_response.status_code == 200
    assert update_status_response.json()["status"] == "finished"

    final_response = client.get(f"/quests/{quest_id}")
    assert final_response.status_code == 200
    assert final_response.json()["status"] == "finished"
