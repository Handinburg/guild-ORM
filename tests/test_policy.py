import pytest
from sqlalchemy import func, select

import models
import schemas
from guild_policy.executor import check_party_rank_gap_policy
from guild_policy.loader import GuildPolicy, get_current_policy
from main import app
from security import create_access_token
from tests.helpers import (
    TestSessionLocal,
    add_member,
    client,
    create_party,
    create_user,
)


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
            "max_rank_gap": 1,
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


@pytest.fixture
def use_rank_gap_policy():
    """给单项测试注入等级差政策，不修改真实 guild_policy.json。"""
    old_override = app.dependency_overrides.get(get_current_policy)

    def override(max_rank_gap):
        policy = GuildPolicy.model_validate(
            {
                "quest": {"max_active_per_party": 3},
                "party": {
                    "max_name_length": 10,
                    "max_rank_gap": max_rank_gap,
                    "forbidden_name_parts": ["admin"],
                },
                "user": {
                    "max_username_length": 10,
                    "max_adventurer_name_length": 10,
                    "forbidden_name_parts": ["admin"],
                },
            }
        )
        app.dependency_overrides[get_current_policy] = lambda: policy

    yield override

    if old_override is None:
        app.dependency_overrides.pop(get_current_policy, None)
    else:
        app.dependency_overrides[get_current_policy] = old_override


def authorization_headers(user_id):
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


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


# 跨级组队政策

@pytest.mark.parametrize(
    ("max_gap", "leader_rank", "candidate_rank", "expected_status"),
    [
        (0, "silver", "silver", 201),
        (0, "silver", "gold", 409),
        (1, "silver", "gold", 201),
        (1, "silver", "platinum", 409),
    ],
)
def test_rank_gap_policy_handles_same_rank_and_exact_boundary(
    use_rank_gap_policy,
    max_gap,
    leader_rank,
    candidate_rank,
    expected_status,
):
    use_rank_gap_policy(max_gap)
    db = TestSessionLocal()
    party = create_party(db, name="边界等级队")
    leader = create_user(db, username="gapleader", adventurer_rank=leader_rank)
    candidate = create_user(
        db,
        username="gapcandidate",
        adventurer_rank=candidate_rank,
    )
    add_member(db, party.id, leader.id, is_leader=True)
    party_id = party.id
    candidate_id = candidate.id
    headers = authorization_headers(leader.id)
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={"user_id": candidate_id},
        headers=headers,
    )

    assert response.status_code == expected_status, response.json()

    db = TestSessionLocal()
    membership = db.scalar(
        select(models.PartyMember).where(
            models.PartyMember.user_id == candidate_id
        )
    )
    if expected_status == 201:
        assert response.json()["user"]["adventurer_rank"] == candidate_rank
        assert membership is not None
    else:
        assert response.json()["detail"].startswith("新成员与小队现有成员的等级差距过大")
        assert membership is None
    db.close()


def test_rank_gap_policy_allows_first_member_for_an_empty_party():
    policy = GuildPolicy.model_validate(
        {
            "quest": {"max_active_per_party": 3},
            "party": {
                "max_name_length": 10,
                "max_rank_gap": 0,
                "forbidden_name_parts": [],
            },
            "user": {
                "max_username_length": 10,
                "max_adventurer_name_length": 10,
                "forbidden_name_parts": [],
            },
        }
    )
    db = TestSessionLocal()
    party = create_party(db, name="空队首人")
    candidate = create_user(db, username="firstmember", adventurer_rank=models.AdventurerRank.GOLD,)
    member_data = check_party_rank_gap_policy(
        party_id=party.id,
        party_member_data=schemas.PartyMemberCreate(user_id=candidate.id),
        db=db,
        current_policy=policy,
    )

    assert member_data.user_id == candidate.id
    assert party.member_list == []
    db.close()


@pytest.mark.parametrize(
    ("candidate_rank", "expected_status"),
    [
        ("iron", 201),
        ("silver", 201),
        ("gold", 201),
        ("platinum", 201),
        ("copper", 409),
        ("mithril", 409),
    ],
)
def test_rank_gap_policy_uses_whole_party_extrema(
    use_rank_gap_policy,
    candidate_rank,
    expected_status,
):
    use_rank_gap_policy(2)
    db = TestSessionLocal()
    party = create_party(db, name="极值等级队")
    leader = create_user(db, username="highleader", adventurer_rank=models.AdventurerRank.GOLD,)
    silver = create_user(db, username="silverbase", adventurer_rank=models.AdventurerRank.SILVER,)
    candidate = create_user(
        db,
        username="extremecand",
        adventurer_rank=candidate_rank,
    )
    add_member(db, party.id, leader.id, is_leader=True)
    add_member(db, party.id, silver.id)
    party_id = party.id
    candidate_id = candidate.id
    headers = authorization_headers(leader.id)
    db.close()

    response = client.post(
        f"/parties/{party_id}/members",
        json={
            "user_id": candidate_id,
            # 额外字段不能冒充数据库里的真实等级。
            "adventurer_rank": "gold",
        },
        headers=headers,
    )

    assert response.status_code == expected_status, response.json()

    if expected_status == 201:
        assert response.json()["user"]["adventurer_rank"] == candidate_rank

    db = TestSessionLocal()
    membership_count = db.scalar(
        select(func.count(models.PartyMember.id)).where(
            models.PartyMember.user_id == candidate_id
        )
    )
    assert membership_count == (1 if expected_status == 201 else 0)
    db.close()
