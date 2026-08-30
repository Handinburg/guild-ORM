from datetime import datetime, timedelta, timezone

import jwt

from security import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    create_access_token,
)
from tests.helpers import client


#这项测试：产生了一个签名有效、当前未过期的Token
#使用服务器密钥能够decode
def test_create_access_token_contains_user_id_and_expiration():
    token = create_access_token(user_id=123)

    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
    )

    assert payload["sub"] == "123"
    assert "exp" in payload

def test_get_current_user_with_valid_token_200():
    register_response = client.post(
        "/users/register",
        json={
            "username": "token_user",
            "adventurer_name": "持票冒险者",
            "password": "test_password",
        },
    )

    assert register_response.status_code == 201

    registered_user = register_response.json()

    login_response = client.post(
        "/users/login",
        json={
            "username": "token_user",
            "password": "test_password",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    # return {
    #     "access_token": access_token,
    #     "token_type": "bearer",
    # }
    me_response = client.get(
        "/users/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )
    #原来是这么发的
    # me_response是 HTTP响应对象 带着状态码什么的属性
    # 他的.json（）方法才是看 路由下函数返回什么

    assert me_response.status_code == 200

    current_user = me_response.json()

    assert current_user["id"] == registered_user["id"]
    assert current_user["username"] == "token_user"
    assert current_user["adventurer_name"] == "持票冒险者"
    assert current_user["is_admin"] is False

    assert "password" not in current_user
    assert "password_hash" not in current_user


# 当前认证需要测试的失败情况
# 情况	                  应由谁拦截	预期
# 1完全没有 Authorization	HTTPBearer	401
# 2使用 Basic 而非 Bearer	HTTPBearer	401
# 3Bearer 后没有 Token	    HTTPBearer	401
# 4Token是一串垃圾文字	    jwt.decode	401
# 5Token结构正确但签名是假的	jwt.decode	401
# 6Token已经过期	            jwt.decode	401
# 7Token缺少 sub	       get_current_user	401
# 8sub 不是整数文本	int(user_id_text)	401
# 9sub 对应的 User不存在	db.get()后判断	401
# 10Token缺少 exp	        验证器应拦截	401
# 11Token使用未允许的算法	algorithms=[...]	401

def test_get_current_user_without_token_401():
    response = client.get(
        "/users/me"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

#“测试断言辅助函数”省的每个打一遍 反正都返回401
def assert_invalid_credentials(response):
    assert response.status_code == 401
    assert response.json() == {"detail": "身份凭证无效"}
    assert response.headers["www-authenticate"] == "Bearer"


def create_test_token(payload, *, key=JWT_SECRET_KEY, algorithm=JWT_ALGORITHM):
    return jwt.encode(payload, key, algorithm=algorithm)


def test_get_current_user_with_malformed_token_401():
    response = client.get(
        "/users/me",
        headers={
            "Authorization": "Bearer not-a-valid-jwt",
        },
    )
    assert_invalid_credentials(response)


def test_get_current_user_rejects_wrong_signature():
    token = create_test_token(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        key="wrong-test-secret-that-is-at-least-32-bytes-long",
    )

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_invalid_credentials(response)


def test_get_current_user_rejects_expired_token():
    token = create_test_token(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
    )

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_invalid_credentials(response)


def test_get_current_user_rejects_token_without_sub():
    token = create_test_token(
        {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
    )

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_invalid_credentials(response)


def test_get_current_user_rejects_token_without_exp():
    token = create_test_token({"sub": "1"})

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_invalid_credentials(response)


def test_get_current_user_rejects_non_integer_sub():
    token = create_test_token(
        {
            "sub": "not-an-integer",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
    )

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_invalid_credentials(response)


def test_get_current_user_rejects_missing_user():
    token = create_test_token(
        {
            "sub": "999999",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
    )

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_invalid_credentials(response)


def test_get_current_user_rejects_basic_authorization():
    response = client.get(
        "/users/me",
        headers={"Authorization": "Basic dXNlcjpwYXNzd29yZA=="},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_get_current_user_rejects_unapproved_algorithm():
    token = create_test_token(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        key="test-key-for-hs384-that-is-at-least-48-bytes-long-123456",
        algorithm="HS384",
    )

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert_invalid_credentials(response)
