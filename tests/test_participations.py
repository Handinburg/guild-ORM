from sqlalchemy import select

import models
from security import create_access_token
import pytest
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


def create_leader_access_token(db, party_id, *, username):
    leader = create_user(db, username=username)
    add_member(db, party_id, leader.id, is_leader=True)
    return create_access_token(leader.id)


def test_party_accepts_quest():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(db, title="低级任务", category_id=category.id, status="open")
    party = create_party(db, name="接任务小队")
    access_token = create_leader_access_token(
        db,
        party.id,
        username="accept_quest_leader",
    )
    quest_id = quest.id
    party_id = party.id
    db.close()

    response = client.post(
        f"/parties/{party_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["party_id"] == party_id
    assert data["quest_id"] == quest_id

    quest_response = client.get(f"/quests/{quest_id}")
    assert quest_response.status_code == 200
    assert quest_response.json()["status"] == "commenced"


def test_leader_cannot_accept_quest_for_another_party_returns_403():
    db = TestSessionLocal()
    category = create_category(db, name="护送")
    quest = create_quest(db, title="护送木车", category_id=category.id, status="open")
    own_party = create_party(db, name="接任务队长自己的小队")
    access_token = create_leader_access_token(
        db,
        own_party.id,
        username="cross_party_quest_leader",
    )
    quest_id = quest.id
    db.close()

    response = client.post(
        f"/parties/99999/quests/{quest_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "不是这个小队"}


def test_accept_quest_missing_quest_returns_404():
    db = TestSessionLocal()
    party = create_party(db, name="空任务队")
    access_token = create_leader_access_token(
        db,
        party.id,
        username="missing_quest_leader",
    )
    party_id = party.id
    db.close()

    response = client.post(
        f"/parties/{party_id}/quests/999999",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "任务不存在"}


def test_same_party_cannot_accept_same_quest_twice():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(db, title="重复接取", category_id=category.id, status="open")
    party = create_party(db, name="重复接取队")
    access_token = create_leader_access_token(
        db,
        party.id,
        username="duplicate_accept_leader",
    )
    party_id = party.id
    quest_id = quest.id
    db.close()

    headers = {"Authorization": f"Bearer {access_token}"}
    first = client.post(f"/parties/{party_id}/quests/{quest_id}", headers=headers)
    second = client.post(f"/parties/{party_id}/quests/{quest_id}", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "该小队已经接受过此任务"}


def test_non_cooperative_quest_cannot_be_accepted_by_second_party_returns_409():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(db, title="独占任务", category_id=category.id, status="open")
    party_a = create_party(db, name="A队")
    party_b = create_party(db, name="B队")
    token_a = create_leader_access_token(db, party_a.id, username="exclusive_leader_a")
    token_b = create_leader_access_token(db, party_b.id, username="exclusive_leader_b")
    party_a_id = party_a.id
    party_b_id = party_b.id
    quest_id = quest.id
    db.close()

    first = client.post(
        f"/parties/{party_a_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    second = client.post(
        f"/parties/{party_b_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "该任务已经被其他小队接受"}


def test_cooperative_quest_allows_multiple_parties():
    db = TestSessionLocal()
    category = create_category(db, name="合作")
    quest = create_quest(db, title="团队副本", category_id=category.id, status="open", is_cooperative=True)
    party_a = create_party(db, name="合作队A")
    party_b = create_party(db, name="合作队B")
    token_a = create_leader_access_token(db, party_a.id, username="cooperative_leader_a")
    token_b = create_leader_access_token(db, party_b.id, username="cooperative_leader_b")
    party_a_id = party_a.id
    party_b_id = party_b.id
    quest_id = quest.id
    db.close()

    response_a = client.post(
        f"/parties/{party_a_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    response_b = client.post(
        f"/parties/{party_b_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )

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
    access_token = create_leader_access_token(
        db,
        party.id,
        username="query_party_quests_leader",
    )
    party_id = party.id
    quest_a_id = quest_a.id
    quest_b_id = quest_b.id
    db.close()

    headers = {"Authorization": f"Bearer {access_token}"}
    client.post(f"/parties/{party_id}/quests/{quest_a_id}", headers=headers)
    client.post(f"/parties/{party_id}/quests/{quest_b_id}", headers=headers)

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
    token_a = create_leader_access_token(db, party_a.id, username="quest_parties_leader_a")
    token_b = create_leader_access_token(db, party_b.id, username="quest_parties_leader_b")
    party_a_id = party_a.id
    party_b_id = party_b.id
    quest_id = quest.id
    db.close()

    client.post(
        f"/parties/{party_a_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    client.post(
        f"/parties/{party_b_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )

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
    access_token = create_leader_access_token(
        db,
        party.id,
        username="withdraw_quest_leader",
    )
    quest_id = quest.id
    party_id = party.id
    db.close()

    headers = {"Authorization": f"Bearer {access_token}"}
    client.post(f"/parties/{party_id}/quests/{quest_id}", headers=headers)

    response = client.delete(f"/parties/{party_id}/quests/{quest_id}", headers=headers)

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
    access_token = create_leader_access_token(
        db,
        party.id,
        username="missing_participation_leader",
    )
    quest_id = quest.id
    party_id = party.id
    db.close()

    response = client.delete(
        f"/parties/{party_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "该小队没有参与此任务"}


def test_last_party_withdraw_reopens_quest():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    quest = create_quest(db, title="最终任务", category_id=category.id, status="open")
    party = create_party(db, name="最后一个队")
    access_token = create_leader_access_token(
        db,
        party.id,
        username="last_withdraw_leader",
    )
    party_id = party.id
    quest_id = quest.id
    db.close()

    headers = {"Authorization": f"Bearer {access_token}"}
    client.post(f"/parties/{party_id}/quests/{quest_id}", headers=headers)
    response = client.delete(f"/parties/{party_id}/quests/{quest_id}", headers=headers)

    assert response.status_code == 204
    check_response = client.get(f"/quests/{quest_id}")
    assert check_response.status_code == 200
    assert check_response.json()["status"] == "open"

def test_party_does_quest_flow():
    db = TestSessionLocal()

    admin_user = create_user(db,is_admin=True)
    access_token = create_access_token(admin_user.id)

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
    leader_access_token = create_access_token(user.id)
    db.close()

    accept_response = client.post(
        f"/parties/{party_id}/quests/{quest_id}",
        headers={"Authorization": f"Bearer {leader_access_token}"},
    )
    assert accept_response.status_code == 201

    party_quests = client.get(f"/parties/{party_id}/quests")
    assert party_quests.status_code == 200
    assert any(item["id"] == quest_id for item in party_quests.json())
    #返回的任务列表中，只要有一个任务的 ID 等于刚才那个任务 ID，就通过。
    update_status_response = client.patch(
        f"/quests/{quest_id}/status",
        json={"status": "finished"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert update_status_response.status_code == 200
    assert update_status_response.json()["status"] == "finished"

    final_response = client.get(f"/quests/{quest_id}")
    assert final_response.status_code == 200
    assert final_response.json()["status"] == "finished"


@pytest.mark.parametrize("method", ["POST", "DELETE"])
#下面这个测试运行两次，第一次把 method 设为 "POST"，第二次设为 "DELETE"。
def test_participation_leader_routes_without_login_return_401(method):
    response = client.request(method, "/parties/999/quests/999")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_participation_leader_routes_reject_ordinary_member_403(method):
    db = TestSessionLocal()
    party = create_party(db, name="普通成员不能操作参与关系")
    ordinary_user = create_user(db, username="ordinary_participation_member")
    add_member(db, party.id, ordinary_user.id, is_leader=False)
    party_id = party.id
    access_token = create_access_token(ordinary_user.id)
    db.close()

    response = client.request(
        method,
        f"/parties/{party_id}/quests/999",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要队长权限"}


# 接取任务等级门槛

@pytest.mark.parametrize(
    ("party_rank", "minimum_rank", "expected_status"),
    [
        ("silver", "silver", 201),
        ("gold", "silver", 201),
        ("iron", "silver", 403),
    ],
)
def test_accept_quest_compares_business_rank_order_and_has_no_failure_side_effects(
    party_rank,
    minimum_rank,
    expected_status,
):
    db = TestSessionLocal()
    category = create_category(db, name="接取等级")
    quest = create_quest(
        db,
        title="等级门槛任务",
        category_id=category.id,
        minimum_rank=minimum_rank,
    )
    party = create_party(db, name="接取等级队")
    leader = create_user(db, username="rankleader", adventurer_rank=party_rank)
    add_member(db, party.id, leader.id, is_leader=True)
    quest_id = quest.id
    party_id = party.id
    headers = authorization_headers(leader.id)
    db.close()

    response = client.post(
        f"/parties/{party_id}/quests/{quest_id}",
        headers=headers,
    )

    assert response.status_code == expected_status, response.json()

    db = TestSessionLocal()
    participation = db.scalar(
        select(models.Participation).where(
            models.Participation.party_id == party_id,
            models.Participation.quest_id == quest_id,
        )
    )
    stored_quest = db.get(models.Quest, quest_id)
    assert stored_quest is not None
    if expected_status == 201:
        assert participation is not None
        assert stored_quest.status == "commenced"
    else:
        assert response.json() == {"detail": "小队等级不足，无法接取该任务"}
        assert participation is None
        assert stored_quest.status == "open"
    db.close()


def test_accept_quest_uses_highest_member_and_recalculates_after_downgrade():
    db = TestSessionLocal()
    category = create_category(db, name="动态接取")
    first_quest = create_quest(
        db,
        title="降级前任务",
        category_id=category.id,
        minimum_rank=models.AdventurerRank.GOLD,
    )
    second_quest = create_quest(
        db,
        title="降级后任务",
        category_id=category.id,
        minimum_rank=models.AdventurerRank.GOLD,
    )
    party = create_party(db, name="动态接取队")
    leader = create_user(db, username="lowleader", adventurer_rank=models.AdventurerRank.COPPER,)
    strongest = create_user(db, username="strongest", adventurer_rank=models.AdventurerRank.GOLD,)
    admin = create_user(db, username="rankmaster", is_admin=True)
    add_member(db, party.id, leader.id, is_leader=True)
    add_member(db, party.id, strongest.id)
    first_quest_id = first_quest.id
    second_quest_id = second_quest.id
    party_id = party.id
    strongest_id = strongest.id
    leader_headers = authorization_headers(leader.id)
    admin_headers = authorization_headers(admin.id)
    db.close()

    first_accept_response = client.post(
        f"/parties/{party_id}/quests/{first_quest_id}",
        headers=leader_headers,
    )
    downgrade_response = client.patch(
        f"/users/{strongest_id}/rank",
        json={"adventurer_rank": "silver"},
        headers=admin_headers,
    )
    accept_response = client.post(
        f"/parties/{party_id}/quests/{second_quest_id}",
        headers=leader_headers,
    )

    assert first_accept_response.status_code == 201, first_accept_response.json()
    assert downgrade_response.status_code == 200, downgrade_response.json()
    assert accept_response.status_code == 403

    db = TestSessionLocal()
    participation = db.scalar(
        select(models.Participation).where(
            models.Participation.party_id == party_id,
            models.Participation.quest_id == second_quest_id,
        )
    )
    stored_quest = db.get(models.Quest, second_quest_id)
    assert participation is None
    assert stored_quest is not None
    assert stored_quest.status == "open"
    db.close()
