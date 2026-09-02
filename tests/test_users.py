from sqlalchemy import select

import models
from security import create_access_token, verify_password
from tests.helpers import TestSessionLocal, client, create_user


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
