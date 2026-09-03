from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import pytest

import models
from security import create_access_token, verify_password
from tests.helpers import (
    TestSessionLocal,
    add_member,
    client,
    create_category,
    create_party,
    create_quest,
    create_user,
)


def authorization_headers(user_id):
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


def test_register_user_201():
    response = client.post(
        "/users/register",
        json={
            "username": "wild_rat",
            "adventurer_name": "测试吱吱",
            "password": "guild12345",
        },
    )

    assert response.status_code == 201, response.json()

    data = response.json()

    assert data["username"] == "wild_rat"
    assert data["adventurer_name"] == "测试吱吱"
    assert data["is_admin"] is False

    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data

    db = TestSessionLocal()
    stored_user = db.scalar(
        select(models.User).where(
            models.User.username == "wild_rat"
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
            "username": "member1",
            "adventurer_name": "普通冒险者",
            "password": "guild12345",
            "is_admin": True,
        },
    )

    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["is_admin"] is False
    assert "password" not in data
    assert "password_hash" not in data

    db = TestSessionLocal()
    stored_user = db.scalar(
        select(models.User).where(
            models.User.username == "member1"
        )
    )
    assert stored_user is not None
    assert stored_user.is_admin is False
    db.close()

def test_register_duplicate_username_409():
    user_data = {
        "username": "dup_rat",
        "adventurer_name": "重复鼠",
        "password": "guild12345",
    }

    first_response = client.post(
        "/users/register",
        json=user_data,
    )

    assert first_response.status_code == 201, first_response.json()

    second_response = client.post(
        "/users/register",
        json=user_data,
    )

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "用户名已存在"
    }


def test_database_rejects_duplicate_username():
    db = TestSessionLocal()
    create_user(db, username="dbunique")
    duplicate = models.User(
        username="dbunique",
        adventurer_name="另一个冒险者",
        password_hash="placeholder_hash",
        is_admin=False,
    )
    db.add(duplicate)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()
    users = db.scalars(
        select(models.User).where(models.User.username == "dbunique")
    ).all()
    assert len(users) == 1
    db.close()

#登录接口没问题 确实能verify 稍微看看jwt 别错得太离谱
def test_user_login_200():
    register_response = client.post(
        "/users/register",
        json={
            "username": "Handinburg",
            "adventurer_name": "Dingburg",
            "password": "test_password",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/users/login",
        json={
            "username": "Handinburg",
            "password": "test_password",
        },
    )
    data= login_response.json()
    assert login_response.status_code == 200
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    #这个值是不是 str这种类型的实例。比type（）更宽容
    assert data["access_token"] != ""

    assert "password" not in data
    assert "password_hash" not in data

def test_login_wrong_username_or_passsword_401():
    register_response = client.post(
        "/users/register",
        json={
            "username": "Handinburg",
            "adventurer_name": "Dingburg",
            "password": "test_password",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/users/login",
        json={
            "username": "Handinburg",
            "password": "wrong_password",
        },
    )
    assert login_response.status_code == 401
    assert login_response.json() == {
            "detail": "用户名或密码错误"
        }

    login_response = client.post(
            "/users/login",
            json={
                "username": "DinburgHan",
                "password": "test_password",
            },
        )
    assert login_response.status_code == 401
    assert login_response.json() == {
                "detail": "用户名或密码错误"
            }


# 用户等级

def test_registration_defaults_to_copper_and_cannot_self_assign_rank():
    response = client.post(
        "/users/register",
        json={
            "username": "newranker",
            "adventurer_name": "新冒险者",
            "password": "guild12345",
            "adventurer_rank": "adamantite",
        },
    )

    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["adventurer_rank"] == "copper"
    assert "password" not in data
    assert "password_hash" not in data

    db = TestSessionLocal()
    user = db.scalar(
        select(models.User).where(models.User.username == "newranker")
    )

    assert user is not None
    assert user.adventurer_rank == "copper"
    db.close()


def test_admin_can_upgrade_downgrade_and_idempotently_set_user_rank():
    db = TestSessionLocal()
    admin = create_user(db, username="rankboss", is_admin=True)
    user = create_user(db, username="rankuser")
    user_id = user.id
    headers = authorization_headers(admin.id)
    db.close()

    for requested_rank in ("gold", "silver", "silver"):
        response = client.patch(
            f"/users/{user_id}/rank",
            json={"adventurer_rank": requested_rank},
            headers=headers,
        )

        assert response.status_code == 200, response.json()
        assert response.json()["adventurer_rank"] == requested_rank
        assert "password_hash" not in response.json()

        db = TestSessionLocal()
        stored_user = db.get(models.User, user_id)
        assert stored_user is not None
        assert stored_user.adventurer_rank == requested_rank
        db.close()


def test_update_user_rank_requires_login_401():
    response = client.patch(
        "/users/1/rank",
        json={"adventurer_rank": "gold"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_update_user_rank_requires_admin_403_and_does_not_mutate():
    db = TestSessionLocal()
    ordinary_user = create_user(db, username="ranknormal")
    target = create_user(db, username="ranktarget")
    target_id = target.id
    headers = authorization_headers(ordinary_user.id)
    db.close()

    response = client.patch(
        f"/users/{target_id}/rank",
        json={"adventurer_rank": "gold"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要管理员权限"}

    db = TestSessionLocal()
    stored_target = db.get(models.User, target_id)
    assert stored_target is not None
    assert stored_target.adventurer_rank == "copper"
    db.close()


def test_update_missing_user_rank_returns_404():
    db = TestSessionLocal()
    admin = create_user(db, username="rankowner", is_admin=True)
    headers = authorization_headers(admin.id)
    db.close()

    response = client.patch(
        "/users/999999/rank",
        json={"adventurer_rank": "gold"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "用户不存在"}


def test_update_user_rank_rejects_unknown_enum_value_422():
    db = TestSessionLocal()
    admin = create_user(db, username="rankadmin", is_admin=True)
    user = create_user(db, username="rankinvalid")
    headers = authorization_headers(admin.id)
    user_id = user.id
    db.close()

    response = client.patch(
        f"/users/{user_id}/rank",
        json={"adventurer_rank": "diamond"},
        headers=headers,
    )

    assert response.status_code == 422

    db = TestSessionLocal()
    stored_user = db.get(models.User, user_id)
    assert stored_user is not None
    assert stored_user.adventurer_rank == "copper"
    db.close()


def test_admin_user_list_and_detail_are_stably_paginated_and_hide_passwords():
    db = TestSessionLocal()
    admin = create_user(db, username="userqueryadmin", is_admin=True)
    first = create_user(db, username="queryuser1")
    second = create_user(db, username="queryuser2")
    headers = authorization_headers(admin.id)
    first_id = first.id
    second_id = second.id
    db.close()

    list_response = client.get(
        "/users",
        params={"limit": 1, "offset": 2},
        headers=headers,
    )
    detail_response = client.get(f"/users/{first_id}", headers=headers)

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [second_id]
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == first_id
    assert "password" not in detail_response.json()
    assert "password_hash" not in detail_response.json()


@pytest.mark.parametrize("path", ["/users", "/users/999999"])
def test_admin_user_queries_reject_unauthenticated_and_normal_users(path):
    without_login = client.get(path)

    db = TestSessionLocal()
    normal_user = create_user(db, username="userquerynormal")
    headers = authorization_headers(normal_user.id)
    db.close()
    without_admin = client.get(path, headers=headers)

    assert without_login.status_code == 401
    assert without_admin.status_code == 403


def test_admin_user_detail_missing_returns_404():
    db = TestSessionLocal()
    admin = create_user(db, username="missinguseradmin", is_admin=True)
    headers = authorization_headers(admin.id)
    db.close()

    response = client.get("/users/999999", headers=headers)

    assert response.status_code == 404


def test_my_alive_quests_returns_empty_list_when_user_has_no_party():
    db = TestSessionLocal()
    user = create_user(db, username="solouser")
    headers = authorization_headers(user.id)
    db.close()

    response = client.get(
        "/users/me/quests/alive",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_my_alive_quests_returns_only_participated_alive_statuses():
    db = TestSessionLocal()
    category = create_category(db, name="我的进行中")
    party = create_party(db, name="进行中查询队")
    user = create_user(db, username="aliveuser")
    add_member(db, party.id, user.id, is_leader=True)

    for status in models.QuestStatus:
        quest = create_quest(
            db,
            title=f"状态-{status.value}",
            category_id=category.id,
            status=status.value,
        )
        db.add(
            models.Participation(
                party_id=party.id,
                quest_id=quest.id,
            )
        )

    db.commit()
    headers = authorization_headers(user.id)
    db.close()

    response = client.get(
        "/users/me/quests/alive",
        headers=headers,
    )

    assert response.status_code == 200
    assert {quest["status"] for quest in response.json()} == {
        "recruiting",
        "commenced",
        "postponed",
    }


def test_my_available_quests_returns_404_when_user_has_no_party():
    db = TestSessionLocal()
    user = create_user(db, username="noavailable")
    headers = authorization_headers(user.id)
    db.close()

    response = client.get(
        "/users/me/quests/available",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "当前用户没有加入小队"}


def test_my_available_quests_returns_empty_list_when_nothing_matches():
    db = TestSessionLocal()
    category = create_category(db, name="无可接任务")
    create_quest(
        db,
        title="等级不足",
        category_id=category.id,
        minimum_rank=models.AdventurerRank.GOLD,
    )
    party = create_party(db, name="铜级查询队")
    user = create_user(db, username="nomatching")
    add_member(db, party.id, user.id, is_leader=True)
    headers = authorization_headers(user.id)
    db.close()

    response = client.get("/users/me/quests/available", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_my_available_quests_applies_status_participation_and_rank_filters():
    db = TestSessionLocal()
    category = create_category(db, name="可接任务")
    party = create_party(db, name="可接查询队")
    user = create_user(
        db,
        username="available",
        adventurer_rank=models.AdventurerRank.SILVER,
    )
    add_member(db, party.id, user.id, is_leader=True)

    copper_quest = create_quest(
        db,
        title="铜级可接",
        category_id=category.id,
        minimum_rank=models.AdventurerRank.COPPER,
    )
    silver_quest = create_quest(
        db,
        title="银级边界可接",
        category_id=category.id,
        minimum_rank=models.AdventurerRank.SILVER,
    )
    create_quest(
        db,
        title="黄金等级不足",
        category_id=category.id,
        minimum_rank=models.AdventurerRank.GOLD,
    )
    create_quest(
        db,
        title="已经开始",
        category_id=category.id,
        status=models.QuestStatus.COMMENCED.value,
        minimum_rank=models.AdventurerRank.COPPER,
    )
    accepted_quest = create_quest(
        db,
        title="本队已经接取",
        category_id=category.id,
        minimum_rank=models.AdventurerRank.COPPER,
    )
    db.add(
        models.Participation(
            party_id=party.id,
            quest_id=accepted_quest.id,
        )
    )
    db.commit()
    headers = authorization_headers(user.id)
    expected_ids = {copper_quest.id, silver_quest.id}
    participation_count_before = len(party.participation_list)
    party_id = party.id
    db.close()

    response = client.get(
        "/users/me/quests/available",
        headers=headers,
    )

    assert response.status_code == 200
    assert {quest["id"] for quest in response.json()} == expected_ids
    assert {quest["status"] for quest in response.json()} == {"recruiting"}

    db = TestSessionLocal()
    stored_party = db.get(models.Party, party_id)

    assert stored_party is not None
    assert len(stored_party.participation_list) == participation_count_before
    db.close()

    login_response = client.post(
                "/users/login",
                json={
                    "username": "123",
                    "password": "wrong_password",
                },
            )
    assert login_response.status_code == 401
    assert login_response.json() == {
                "detail": "用户名或密码错误"
            }
