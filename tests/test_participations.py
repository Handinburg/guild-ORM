from security import create_access_token
from tests.helpers import (
    TestSessionLocal,
    add_member,
    client,
    create_category,
    create_party,
    create_quest,
    create_user,
)


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
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert update_status_response.status_code == 200
    assert update_status_response.json()["status"] == "finished"

    final_response = client.get(f"/quests/{quest_id}")
    assert final_response.status_code == 200
    assert final_response.json()["status"] == "finished"
