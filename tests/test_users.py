from sqlalchemy import select

import models
from security import verify_password
from tests.helpers import TestSessionLocal, client


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
