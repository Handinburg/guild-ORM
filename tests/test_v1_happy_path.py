import models

from tests.helpers import (
    TestSessionLocal,
    authorization_headers,
    client,
    create_category,
    create_user,
)


def test_v1_complete_happy_path():
    # 只有管理员无法通过公开注册获得，
    # 任务类别目前也没有纳入本次业务流程，
    # 所以这两项直接作为测试前置数据。
    db = TestSessionLocal()

    admin = create_user(
        db,
        username="admin",
        adventurer_name="管理员",
        is_admin=True,
    )
    category = create_category(
        db,
        name="讨伐",
    )

    admin_headers = authorization_headers(admin.id)
    category_id = category.id

    db.close()

    # 1. 注册未来的队长
    leader_register_response = client.post(
        "/users/register",
        json={
            "username": "leader",
            "adventurer_name": "白银队长",
            "password": "leader_password",
        },
    )

    assert leader_register_response.status_code == 201

    leader_data = leader_register_response.json()
    leader_user_id = leader_data["id"]

    # 2. 注册普通成员
    member_register_response = client.post(
        "/users/register",
        json={
            "username": "member",
            "adventurer_name": "铜牌成员",
            "password": "member_password",
        },
    )

    assert member_register_response.status_code == 201

    member_data = member_register_response.json()
    member_user_id = member_data["id"]

    # 3. 队长登录，获得自己的JWT
    leader_login_response = client.post(
        "/users/login",
        json={
            "username": "leader",
            "password": "leader_password",
        },
    )

    assert leader_login_response.status_code == 200

    leader_access_token = (
        leader_login_response.json()["access_token"]
    )
    leader_headers = {
        "Authorization": f"Bearer {leader_access_token}",
    }

    # 4. 普通成员登录
    member_login_response = client.post(
        "/users/login",
        json={
            "username": "member",
            "password": "member_password",
        },
    )

    assert member_login_response.status_code == 200

    member_access_token = (
        member_login_response.json()["access_token"]
    )
    member_headers = {
        "Authorization": f"Bearer {member_access_token}",
    }

    # 5. 管理员创建小队，并指定首任队长
    party_response = client.post(
        "/parties",
        json={
            "name": "幸福小队",
            "leader_user_id": leader_user_id,
        },
        headers=admin_headers,
    )

    assert party_response.status_code == 201

    party_data = party_response.json()
    party_id = party_data["id"]

    # 6. 队长添加普通成员
    add_member_response = client.post(
        f"/parties/{party_id}/members",
        json={
            "user_id": member_user_id,
        },
        headers=leader_headers,
    )

    assert add_member_response.status_code == 201

    # 7. 管理员创建一个铜牌任务
    quest_response = client.post(
        "/quests",
        json={
            "title": "清理史莱姆",
            "description": "城外出现了史莱姆",
            "completion_criteria": "清理全部史莱姆",
            "category_id": category_id,
            "minimum_rank": "copper",
        },
        headers=admin_headers,
    )

    assert quest_response.status_code == 201

    quest_data = quest_response.json()
    quest_id = quest_data["id"]

    assert quest_data["status"] == "recruiting"

    # 8. 队长查看可接任务
    available_response = client.get(
        "/users/me/quests/available",
        headers=leader_headers,
    )

    assert available_response.status_code == 200

    available_quest_ids = [
        quest["id"]
        for quest in available_response.json()
    ]

    assert quest_id in available_quest_ids

    # 9. 队长代表小队接取任务
    accept_response = client.post(
        f"/parties/{party_id}/quests/{quest_id}",
        headers=leader_headers,
    )

    assert accept_response.status_code == 201

    # 10. 已接任务不再出现在“我的可接任务”中
    available_response = client.get(
        "/users/me/quests/available",
        headers=leader_headers,
    )

    assert available_response.status_code == 200

    available_quest_ids = [
        quest["id"]
        for quest in available_response.json()
    ]

    assert quest_id not in available_quest_ids

    # 11. 同队普通成员能够看到进行中的任务
    alive_response = client.get(
        "/users/me/quests/alive",
        headers=member_headers,
    )

    assert alive_response.status_code == 200

    alive_quest_ids = [
        quest["id"]
        for quest in alive_response.json()
    ]

    assert quest_id in alive_quest_ids

    # 12. 管理员把任务改为commenced
    status_response = client.patch(
        f"/quests/{quest_id}/status",
        json={
            "status": "commenced",
        },
        headers=admin_headers,
    )

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "commenced"

    # 13. commenced仍属于alive
    alive_response = client.get(
        "/users/me/quests/alive",
        headers=member_headers,
    )

    assert alive_response.status_code == 200

    alive_quest_ids = [
        quest["id"]
        for quest in alive_response.json()
    ]

    assert quest_id in alive_quest_ids

    # 14. 队长解除Participation
    withdraw_response = client.delete(
        f"/parties/{party_id}/quests/{quest_id}",
        headers=leader_headers,
    )

    assert withdraw_response.status_code == 204
    assert withdraw_response.content == b""

    # 15. 解除后，小队成员不再看到该任务
    alive_response = client.get(
        "/users/me/quests/alive",
        headers=member_headers,
    )

    assert alive_response.status_code == 200
    assert alive_response.json() == []

    # 16. 管理员删除整个小队
    delete_party_response = client.delete(
        f"/parties/{party_id}",
        headers=admin_headers,
    )

    assert delete_party_response.status_code == 204
    assert delete_party_response.content == b""

    # 17. 最后回查数据库
    db = TestSessionLocal()

    assert db.get(models.Party, party_id) is None

    remaining_members = db.query(
        models.PartyMember
    ).filter(
        models.PartyMember.party_id == party_id
    ).all()

    remaining_participations = db.query(
        models.Participation
    ).filter(
        models.Participation.party_id == party_id
    ).all()

    assert remaining_members == []
    assert remaining_participations == []

    # 删小队不能误删用户和任务
    assert db.get(models.User, leader_user_id) is not None
    assert db.get(models.User, member_user_id) is not None
    assert db.get(models.Quest, quest_id) is not None

    db.close()