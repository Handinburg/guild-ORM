from sqlalchemy import select
import pytest

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
    leader_user = create_user(db, username="first_party_leader")
    leader_user_id = leader_user.id
    access_token = create_access_token(admin_user.id)
    db.close()

    response = client.post(
        "/parties",
        json={
            "name": "自动测试小队",
            "leader_user_id": leader_user_id,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "自动测试小队"
    assert len(data["member_list"]) == 1
    assert data["member_list"][0]["user_id"] == leader_user_id
    assert data["member_list"][0]["is_leader"] is True

    db = TestSessionLocal()
    party = db.get(models.Party, data["id"])
    first_member = db.scalar(
        select(models.PartyMember).where(
            models.PartyMember.party_id == data["id"]
        )
    )

    assert party is not None
    assert first_member is not None
    assert first_member.user_id == leader_user_id
    assert first_member.is_leader is True
    db.close()


def test_create_duplicate_party_returns_409():
#先给db里加一条 100%成功 不需返回201
    db = TestSessionLocal()
    create_party(db, name="银丝鸟")
    admin_user = create_user(db, username="duplicate_party_admin", is_admin=True)
    leader_user = create_user(db, username="duplicate_party_candidate_leader")
    leader_user_id = leader_user.id
    access_token = create_access_token(admin_user.id)
    db.close()
#在真正测试我们想要的409
    response = client.post(
        "/parties",
        json={
            "name": "银丝鸟",
            "leader_user_id": leader_user_id,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "小队名称已存在"}


def test_create_party_requires_admin_403():
    db = TestSessionLocal()
    normal_user = create_user(db, username="normal_party_creator")
    leader_user = create_user(db, username="normal_creator_candidate_leader")
    leader_user_id = leader_user.id
    access_token = create_access_token(normal_user.id)
    db.close()

    response = client.post(
        "/parties",
        json={
            "name": "普通小队",
            "leader_user_id": leader_user_id,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要管理员权限"}

    db = TestSessionLocal()
    party = db.scalar(
        select(models.Party).where(
            models.Party.name == "普通小队"
        )
    )

    assert party is None
    db.close()


def test_create_party_without_login_returns_401():
    response = client.post(
        "/parties",
        json={
            "name": "未登录不能创建的小队",
            "leader_user_id": 999999,
        },
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


def test_create_party_with_missing_leader_returns_404():
    db = TestSessionLocal()
    admin_user = create_user(db, username="missing_leader_admin", is_admin=True)
    access_token = create_access_token(admin_user.id)
    db.close()

    response = client.post(
        "/parties",
        json={
            "name": "没有首任队长的小队",
            "leader_user_id": 999999,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "初始队长用户不存在"}

    db = TestSessionLocal()
    party = db.scalar(
        select(models.Party).where(
            models.Party.name == "没有首任队长的小队"
        )
    )

    assert party is None
    db.close()


def test_create_party_rejects_leader_already_in_another_party_409():
    db = TestSessionLocal()
    admin_user = create_user(db, username="occupied_leader_admin", is_admin=True)
    existing_party = create_party(db, name="候选队长原来的小队")
    occupied_user = create_user(db, username="occupied_leader")
    add_member(db, existing_party.id, occupied_user.id, is_leader=True)
    existing_party_id = existing_party.id
    occupied_user_id = occupied_user.id
    access_token = create_access_token(admin_user.id)
    db.close()

    response = client.post(
        "/parties",
        json={
            "name": "不应创建的新小队",
            "leader_user_id": occupied_user_id,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "该用户已经加入其他小队"}

    db = TestSessionLocal()
    party = db.scalar(
        select(models.Party).where(
            models.Party.name == "不应创建的新小队"
        )
    )
    memberships = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.user_id == occupied_user_id
        )
    ).all()

    assert party is None
    assert len(memberships) == 1
    assert memberships[0].party_id == existing_party_id
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
    leader = create_user(db, username="delete_party_leader")
    add_member(db, party.id, leader.id, is_leader=True)
    party_id = party.id
    access_token = create_access_token(leader.id)
    db.close()

    response = client.delete(
        f"/parties/{party_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 204
    assert response.content == b""
#表示一个空的 bytes，也就是零字节：什么都没有返回
#你必须没有偷偷返回 JSON 或其他内容。
    check_response = client.get(f"/parties/{party_id}")
    assert check_response.status_code == 404
    assert check_response.json() == {"detail": "小队不存在"}


def test_leader_cannot_delete_another_party_returns_403():
    db = TestSessionLocal()
    own_party = create_party(db, name="队长自己的小队")
    leader = create_user(db, username="cross_party_delete_leader")
    add_member(db, own_party.id, leader.id, is_leader=True)
    access_token = create_access_token(leader.id)
    db.close()

    response = client.delete(
        "/parties/999999",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "不是这个小队"}


# 二、小队成员功能

def test_add_member_to_existing_party():
    db = TestSessionLocal()
    admin_user = create_user(db, username="add_member_admin", is_admin=True)
    leader = create_user(db, username="add_member_leader")
    user = create_user(db, username="勇者")
    admin_access_token = create_access_token(admin_user.id)
    leader_id = leader.id
    user_id = user.id
    access_token = create_access_token(leader_id)
    db.close()

    create_response = client.post(
        "/parties",
        json={
            "name": "战队",
            "leader_user_id": leader_id,
        },
        headers={"Authorization": f"Bearer {admin_access_token}"},
    )

    assert create_response.status_code == 201
    party_id = create_response.json()["id"]

    response = client.post(
        f"/parties/{party_id}/members",
        json={"user_id": user_id, "is_leader": False},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["party_id"] == party_id
    assert data["user_id"] == user_id
    assert data["is_leader"] is False
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


def test_leader_cannot_add_member_to_another_party_returns_403():
    db = TestSessionLocal()
    own_party = create_party(db, name="加人队长自己的小队")
    leader = create_user(db, username="cross_party_add_leader")
    add_member(db, own_party.id, leader.id, is_leader=True)
    user = create_user(db, username="cross_party_target")
    access_token = create_access_token(leader.id)
    user_id = user.id
    db.close()

    response = client.post(
        "/parties/999999/members",
        json={"user_id": user_id, "is_leader": False},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "不是这个小队"}


def test_add_missing_user_to_party_returns_404():
    db = TestSessionLocal()
    party = create_party(db, name="缺人小队")
    leader = create_user(db, username="missing_user_leader")
    add_member(db, party.id, leader.id, is_leader=True)
    party_id = party.id
    access_token = create_access_token(leader.id)
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={"user_id": 999999, "is_leader": False},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "用户不存在"}


def test_add_member_rejects_old_character_id_field_422():
    db = TestSessionLocal()
    party = create_party(db, name="旧字段小队")
    leader = create_user(db, username="old_field_leader")
    add_member(db, party.id, leader.id, is_leader=True)
    character = create_character(db, name="独立角色")
    party_id = party.id
    character_id = character.id
    leader_id = leader.id
    access_token = create_access_token(leader.id)
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={"character_id": character_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 422
    db = TestSessionLocal()
    members = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.party_id == party_id
        )
    ).all()
    character = db.get(models.Character, character_id)

    assert len(members) == 1
    assert members[0].user_id == leader_id
    assert character is not None
    db.close()


def test_add_duplicate_member_returns_409():
    db = TestSessionLocal()
    party = create_party(db, name="重复小队")
    leader = create_user(db, username="duplicate_member_leader")
    add_member(db, party.id, leader.id, is_leader=True)
    user = create_user(db, username="重复角色")
    add_member(db, party.id, user.id, is_leader=False)
    party_id = party.id
    user_id = user.id
    access_token = create_access_token(leader.id)
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={"user_id": user_id, "is_leader": False},
        headers={"Authorization": f"Bearer {access_token}"},
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


def test_user_cannot_join_two_parties_409():
    db = TestSessionLocal()
    first_party = create_party(db, name="第一小队")
    second_party = create_party(db, name="第二小队")
    second_party_leader = create_user(db, username="second_party_leader")
    add_member(db, second_party.id, second_party_leader.id, is_leader=True)
    user = create_user(db, username="只能入一队")
    add_member(db, first_party.id, user.id)
    first_party_id = first_party.id
    second_party_id = second_party.id
    user_id = user.id
    access_token = create_access_token(second_party_leader.id)
    db.close()

    response = client.post(
        f"/parties/{second_party_id}/members",
        json={"user_id": user_id},
        headers={"Authorization": f"Bearer {access_token}"},
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
    leader = create_user(db, username="remove_member_leader")
    add_member(db, party.id, leader.id, is_leader=True)
    user = create_user(db, username="离队角色")
    add_member(db, party.id, user.id, is_leader=False)
    party_id = party.id
    user_id = user.id
    access_token = create_access_token(leader.id)
    db.close()

    response = client.delete(
        f"/parties/{party_id}/members/{user_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 204
    assert response.content == b""

    check_response = client.get(f"/parties/{party_id}")
    assert check_response.status_code == 200
    assert all(item["user_id"] != user_id for item in check_response.json()["member_list"])


def test_remove_missing_member_returns_404():
    db = TestSessionLocal()
    party = create_party(db, name="空小队")
    leader = create_user(db, username="remove_missing_leader")
    add_member(db, party.id, leader.id, is_leader=True)
    party_id = party.id
    access_token = create_access_token(leader.id)
    db.close()

    response = client.delete(
        f"/parties/{party_id}/members/999999",
        headers={"Authorization": f"Bearer {access_token}"},
    )

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
    access_token = create_access_token(old_leader.id)
    db.close()

    response = client.patch(
        f"/parties/{party_id}/leader",
        json={"user_id": new_leader_id},
        headers={"Authorization": f"Bearer {access_token}"},
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
    access_token = create_access_token(old_leader.id)
    db.close()

    response = client.patch(
        f"/parties/{party_id}/leader",
        json={"user_id": outsider_id},
        headers={"Authorization": f"Bearer {access_token}"},
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
    access_token = create_access_token(leader.id)
    db.close()

    response = client.patch(
        f"/parties/{party_id}/leader",
        json={"user_id": leader_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "无效修改,此人已是队长"}


@pytest.mark.parametrize(
    ("method", "path", "json_data"),
    [
        ("POST", "/parties/999/members", {"user_id": 999}),
        ("DELETE", "/parties/999/members/999", None),
        ("DELETE", "/parties/999", None),
        ("PATCH", "/parties/999/leader", {"user_id": 999}),
    ],
)
def test_party_leader_routes_without_login_return_401(method, path, json_data):
    response = client.request(method, path, json=json_data)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("method", "path_suffix", "json_data"),
    [
        ("POST", "/members", {"user_id": 999}),
        ("DELETE", "/members/999", None),
        ("DELETE", "", None),
        ("PATCH", "/leader", {"user_id": 999}),
    ],
)
def test_party_leader_routes_reject_ordinary_member_403(
    method,
    path_suffix,
    json_data,
):
    db = TestSessionLocal()
    party = create_party(db, name="普通成员无队长权限")
    ordinary_user = create_user(db, username="ordinary_party_member")
    add_member(db, party.id, ordinary_user.id, is_leader=False)
    party_id = party.id
    access_token = create_access_token(ordinary_user.id)
    db.close()

    response = client.request(
        method,
        f"/parties/{party_id}{path_suffix}",
        json=json_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要队长权限"}

    db = TestSessionLocal()
    party = db.get(models.Party, party_id)

    assert party is not None
    db.close()


# 小队动态等级

def test_party_rank_is_none_when_empty_and_uses_highest_member_not_text_order():
    db = TestSessionLocal()
    party = create_party(db, name="动态等级队")

    assert party.calculate_party_rank() is None

    gold_user = create_user(
        db,
        username="goldmember",
        adventurer_rank=models.AdventurerRank.GOLD,
    )
    silver_user = create_user(
        db,
        username="silvermem",
        adventurer_rank=models.AdventurerRank.SILVER,
    )
    add_member(db, party.id, gold_user.id)
    add_member(db, party.id, silver_user.id)
    db.refresh(party)

    # 字符串字典序会误判 silver > gold；业务顺序必须判定 gold 更高。
    assert party.calculate_party_rank() == models.AdventurerRank.GOLD
    db.close()


def test_party_rank_recalculates_after_member_rank_changes():
    db = TestSessionLocal()
    party = create_party(db, name="重算等级队")
    user = create_user(
        db,
        username="reranker",
        adventurer_rank=models.AdventurerRank.GOLD,
    )
    add_member(db, party.id, user.id, is_leader=True)
    db.refresh(party)

    assert party.calculate_party_rank() == models.AdventurerRank.GOLD

    user.adventurer_rank = models.AdventurerRank.IRON.value
    db.commit()
    db.refresh(party)

    assert party.calculate_party_rank() == models.AdventurerRank.IRON
    db.close()

