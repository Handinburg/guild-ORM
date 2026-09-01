import pytest

from guild_policy_loader import GuildPolicy, get_current_policy
from main import app
from security import create_access_token
from tests.helpers import TestSessionLocal, client, create_user


# 政策模块会在首次导入时读取真实 JSON。
# 这里通过 FastAPI dependency override 注入固定测试政策，
# 不修改真实 guild_policy.json，也不让测试受本机政策文件变化影响。
TEST_POLICY = GuildPolicy.model_validate(
    {
        "quest": {
            "max_active_per_party": 3,
        },
        "party": {
            "max_name_length": 10,
            "forbidden_name_parts": ["admin"],
        },
        "user": {
            "max_username_length": 10,
            "max_adventurer_name_length": 10,
            "forbidden_name_parts": ["admin"],
        },
    }
)


@pytest.fixture(autouse=True)
def override_policy_for_this_module():
    app.dependency_overrides[get_current_policy] = lambda: TEST_POLICY

    yield

    app.dependency_overrides.pop(get_current_policy, None)


def register(username, adventurer_name):
    return client.post(
        "/users/register",
        json={
            "username": username,
            "adventurer_name": adventurer_name,
            "password": "guild12345",
        },
    )


def create_party_request(name):
    db = TestSessionLocal()
    admin_user = create_user(db, username="policyboss", is_admin=True)
    leader_user = create_user(db, username="policylead")
    leader_user_id = leader_user.id
    access_token = create_access_token(admin_user.id)
    db.close()

    return client.post(
        "/parties",
        json={
            "name": name,
            "leader_user_id": leader_user_id,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )


def test_registration_rejects_username_over_max_length():
    response = register(
        username="u" * (TEST_POLICY.user.max_username_length + 1),
        adventurer_name="冒险者",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "用户名过长不能超过10个字"
    }


def test_registration_rejects_adventurer_name_over_max_length():
    response = register(
        username="shortuser",
        adventurer_name="冒" * (TEST_POLICY.user.max_adventurer_name_length + 1),
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "冒险者名过长不能超过10个字"
    }


def test_registration_rejects_whitespace_in_username():
    response = register(
        username="user name",
        adventurer_name="冒险者",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "用户名或冒险者名不能包含空白字符"
    }


def test_registration_rejects_whitespace_in_adventurer_name():
    response = register(
        username="shortuser",
        adventurer_name="冒险 者",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "用户名或冒险者名不能包含空白字符"
    }


def test_registration_rejects_forbidden_username_case_insensitively():
    response = register(
        username="xxAdMiNxx",
        adventurer_name="冒险者",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "用户名包含禁止使用的内容"
    }


def test_registration_rejects_forbidden_adventurer_name():
    response = register(
        username="shortuser",
        adventurer_name="禁admin名",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "冒险者名包含禁止使用的内容"
    }


def test_registration_accepts_names_at_exact_max_length():
    username = "u" * TEST_POLICY.user.max_username_length
    adventurer_name = "冒" * TEST_POLICY.user.max_adventurer_name_length

    response = register(
        username=username,
        adventurer_name=adventurer_name,
    )

    assert response.status_code == 201, response.json()
    assert response.json()["username"] == username
    assert response.json()["adventurer_name"] == adventurer_name


def test_party_policy_rejects_name_over_max_length():
    response = create_party_request(
        "队" * (TEST_POLICY.party.max_name_length + 1)
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "队伍名过长"}


def test_party_policy_rejects_whitespace_in_name():
    response = create_party_request("有 空格")

    assert response.status_code == 400
    assert response.json() == {"detail": "不能包含空白字符"}


def test_party_policy_rejects_forbidden_name():
    response = create_party_request("AdMiN队")

    assert response.status_code == 400
    assert response.json() == {"detail": "包含禁止使用的内容"}


def test_party_policy_accepts_name_at_exact_max_length():
    party_name = "队" * TEST_POLICY.party.max_name_length

    response = create_party_request(party_name)

    assert response.status_code == 201, response.json()
    assert response.json()["name"] == party_name
    assert len(response.json()["member_list"]) == 1
    assert response.json()["member_list"][0]["is_leader"] is True
