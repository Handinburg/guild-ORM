from sqlalchemy import select

import models
from security import create_access_token
from tests.helpers import (
    TestSessionLocal,
    add_member,
    client,
    create_character,
    create_party,
    create_user,
)


# 一、小队功能

def test_get_missing_party_returns_404():
    response = client.get("/parties/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "小队不存在"}


def test_create_party_returns_201_and_checks_data():
    db = TestSessionLocal()
    admin_user = create_user(db, username="create_party_admin", is_admin=True)
    access_token = create_access_token(admin_user.id)
    db.close()

    response = client.post(
        "/parties",
        json={"name": "自动测试小队"},
        headers={"Authorization": f"Bearer {access_token}"},
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
    admin_user = create_user(db, username="duplicate_party_admin", is_admin=True)
    access_token = create_access_token(admin_user.id)
    db.close()
#在真正测试我们想要的409
    response = client.post(
        "/parties",
        json={"name": "银丝鸟"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "小队名称已存在"}


def test_create_party_requires_admin():
    db = TestSessionLocal()
    normal_user = create_user(db, username="normal_party_creator")
    access_token = create_access_token(normal_user.id)
    db.close()

    response = client.post(
        "/parties",
        json={"name": "普通用户不能创建的小队"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要管理员权限"}

    db = TestSessionLocal()
    party = db.scalar(
        select(models.Party).where(
            models.Party.name == "普通用户不能创建的小队"
        )
    )

    assert party is None
    db.close()


def test_create_party_without_login_returns_401():
    response = client.post(
        "/parties",
        json={"name": "未登录不能创建的小队"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    db = TestSessionLocal()
    party = db.scalar(
        select(models.Party).where(
            models.Party.name == "未登录不能创建的小队"
        )
    )

    assert party is None
    db.close()


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
    character = db.get(models.Character, character_id)

    assert character is not None
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
