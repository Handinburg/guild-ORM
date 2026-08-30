import models
from security import create_access_token
from tests.helpers import (
    TestSessionLocal,
    client,
    create_category,
    create_quest,
    create_user,
)


# 三、任务功能

def test_create_quest_returns_201():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    category_id = category.id
    db.close()

    admin_user = create_user(
        db,
        username="quest_admin",
        is_admin=True,
    )
    admin_user_id = admin_user.id
    db.close()

    access_token = create_access_token(admin_user_id)

    response = client.post(
        "/quests",
        json={
            #业务信息
            "title": "讨伐哥布林",
            "description": "村庄附近出现了哥布林",
            "completion_criteria": "消灭5只哥布林",
            "category_id": category_id,
        },
        headers={
            #请求附带信息
        "Authorization": f"Bearer {access_token}",
    },
    
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "讨伐哥布林"
    assert data["category_id"] == category_id
    assert data["status"] == "open"


def test_create_quest_with_missing_category_returns_404():

    db=TestSessionLocal()
    admin_user = create_user(
            db,
            username="quest_admin",
            is_admin=True,
        )
    admin_user_id = admin_user.id
    db.close()
    
    access_token = create_access_token(admin_user_id)
    
    response = client.post(
        "/quests",
        json={
            "title": "讨伐哥布林",
            "description": "村庄附近出现了哥布林",
            "completion_criteria": "消灭5只哥布林",
            "category_id": 999999,
        },
        headers={
        
                "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "任务类别不存在"}

def test_create_quest_with_not_admin_403():
    db=TestSessionLocal()
    not_admin_user = create_user(db)

    access_token = create_access_token(not_admin_user.id)
    db.close()

    response = client.post(
            "/quests",
            json={
                "title": "讨伐哥布林",
                "description": "村庄附近出现了哥布林",
                "completion_criteria": "消灭5只哥布林",
                "category_id": 99,
            },
            headers={
                    "Authorization": f"Bearer {access_token}",
            },
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要管理员权限"} 

def test_create_quest_without_login_401():
    response = client.post(
        "/quests",
        json={
            "title": "讨伐哥布林",
            "description": "村庄附近出现了哥布林",
            "completion_criteria": "消灭5只哥布林",
            "category_id": 99,
        },
    )

    assert response.status_code == 401

def test_get_existing_quest():
    db = TestSessionLocal()
    category = create_category(db, name="采集")
    quest = create_quest(db, title="采集蘑菇", category_id=category.id)
    quest_id = quest.id
    category_id = category.id
    db.close()

    response = client.get(f"/quests/{quest_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == quest_id
    assert data["title"] == "采集蘑菇"
    assert data["category_id"] == category_id


def test_get_missing_quest_returns_404():
    response = client.get("/quests/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "任务不存在"}


def test_update_quest():
    db = TestSessionLocal()
    category = create_category(db, name="护送")
    new_category = create_category(db, name="调查")
    quest = create_quest(db, title="护送商队", category_id=category.id)
    admin_user = create_user(db, username="update_quest_admin", is_admin=True)
    quest_id = quest.id
    new_category_id = new_category.id
    access_token = create_access_token(admin_user.id)
    db.close()

    response = client.patch(
        f"/quests/{quest_id}",
        json={
            "title": "调查遗迹",
            "description": "前往遗迹探索",
            "completion_criteria": "找到地图碎片",
            "category_id": new_category_id,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "调查遗迹"
    assert data["description"] == "前往遗迹探索"
    assert data["completion_criteria"] == "找到地图碎片"
    assert data["category_id"] == new_category_id


def test_update_quest_requires_admin_403():
    db = TestSessionLocal()
    category = create_category(db, name="update_permission_category")
    quest = create_quest(
        db,
        title="ordinary_user_cannot_edit",
        category_id=category.id,
    )
    normal_user = create_user(db, username="normal_quest_editor")
    quest_id = quest.id
    access_token = create_access_token(normal_user.id)
    db.close()

    response = client.patch(
        f"/quests/{quest_id}",
        json={"title": "unauthorized_edit"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要管理员权限"}

    db = TestSessionLocal()
    quest = db.get(
        models.Quest,
        quest_id,
    )

    assert quest is not None
    assert quest.title == "ordinary_user_cannot_edit"
    
    db.close()


def test_update_quest_without_login_returns_401():
    db = TestSessionLocal()
    category = create_category(db, name="update_without_login_category")
    quest = create_quest(
        db,
        title="login_required_to_edit",
        category_id=category.id,
    )
    quest_id = quest.id
    db.close()

    response = client.patch(
        f"/quests/{quest_id}",
        json={"title": "unauthenticated_edit"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    db = TestSessionLocal()
    quest = db.get(models.Quest, quest_id)

    assert quest is not None
    assert quest.title == "login_required_to_edit"
    db.close()


def test_delete_quest():
    db = TestSessionLocal()
    category = create_category(db, name="清理")
    quest = create_quest(db, title="清理洞穴", category_id=category.id)
    admin_user = create_user(db, username="delete_quest_admin", is_admin=True)
    quest_id = quest.id
    access_token = create_access_token(admin_user.id)
    db.close()

    response = client.delete(
        f"/quests/{quest_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 204
    assert response.content == b""

    check_response = client.get(f"/quests/{quest_id}")
    assert check_response.status_code == 404
    assert check_response.json() == {"detail": "任务不存在"}


def test_delete_quest_requires_admin_403():
    db = TestSessionLocal()
    category = create_category(db, name="delete_permission_category")
    quest = create_quest(db, title="ordinary_user_cannot_delete", category_id=category.id)
    normal_user = create_user(db, username="normal_quest_deleter")
    quest_id = quest.id
    access_token = create_access_token(normal_user.id)
    db.close()

    response = client.delete(
        f"/quests/{quest_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要管理员权限"}

    db = TestSessionLocal()
    quest = db.get(models.Quest, quest_id)

    assert quest is not None
    db.close()


def test_delete_quest_without_login_returns_401():
    db = TestSessionLocal()
    category = create_category(db, name="delete_without_login_category")
    quest = create_quest(db, title="login_required_to_delete", category_id=category.id)
    quest_id = quest.id
    db.close()

    response = client.delete(f"/quests/{quest_id}")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    db = TestSessionLocal()
    quest = db.get(models.Quest, quest_id)

    assert quest is not None
    db.close()


def test_filter_quests_by_status():
    db = TestSessionLocal()
    category = create_category(db, name="讨伐")
    create_quest(db, title="A", category_id=category.id, status="open")
    create_quest(db, title="B", category_id=category.id, status="commenced")
    create_quest(db, title="C", category_id=category.id, status="commenced")
    db.close()

    response = client.get("/quests", params={"status": "commenced"})
#GET筛选用 params= POST、PUT、PATCH填表用 json= ID放进网址{}

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {item["title"] for item in data} == {"B", "C"}


def test_filter_quests_by_category_name():
    db = TestSessionLocal()
    category_a = create_category(db, name="讨伐")
    category_b = create_category(db, name="采集")
    create_quest(db, title="讨伐怪物", category_id=category_a.id)
    create_quest(db, title="采集草药", category_id=category_b.id)
    create_quest(db, title="再次讨伐", category_id=category_a.id)
    db.close()

    response = client.get("/quests", params={"category_name": "讨伐"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {item["title"] for item in data} == {"讨伐怪物", "再次讨伐"}


def test_update_quest_status_manually():
    db = TestSessionLocal()
    category = create_category(db, name="调查")
    quest = create_quest(db, title="调查遗迹", category_id=category.id, status="open")
    quest_id = quest.id

    admin_user = create_user(db,is_admin=True)
    access_token = create_access_token(admin_user.id)

    db.close()

    response = client.patch(
        f"/quests/{quest_id}/status",
        json={"status": "finished"
        },
        headers={"Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "finished"


def test_update_quest_status_invalid_returns_400():
    db = TestSessionLocal()
    category = create_category(db, name="护送")
    quest = create_quest(db, title="护送老人", category_id=category.id, status="open")
    quest_id = quest.id

    admin_user = create_user(db,is_admin=True)
    access_token = create_access_token(admin_user.id)
    
    db.close()

    response = client.patch(
        f"/quests/{quest_id}/status",
        json={"status": "not_real"
        },
        headers={"Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["请重新规范输入status 参考管理员手册"]}


# 四、小队参与任务功能

def test_update_quest_status_requires_admi_403():
    db = TestSessionLocal()
    category = create_category(db, name="status_permission_category")
    quest = create_quest(
        db,
        title="status_permission_quest",
        category_id=category.id,
        status="open",
    )
    normal_user = create_user(db, username="normal_status_editor")
    quest_id = quest.id
    access_token = create_access_token(normal_user.id)
    db.close()

    response = client.patch(
        f"/quests/{quest_id}/status",
        json={"status": "finished"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "需要管理员权限"}

    db = TestSessionLocal()
    quest = db.get(
    models.Quest,
    quest_id,
)

    assert quest is not None
    assert quest.status == "open"
    db.close()


def test_update_quest_status_without_login_returns_401():
    db = TestSessionLocal()
    category = create_category(db, name="status_without_login_category")
    quest = create_quest(
        db,
        title="login_required_for_status",
        category_id=category.id,
        status="open",
    )
    quest_id = quest.id
    db.close()

    response = client.patch(
        f"/quests/{quest_id}/status",
        json={"status": "finished"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    db = TestSessionLocal()
    quest = db.get(models.Quest, quest_id)

    assert quest is not None
    assert quest.status == "open"
    db.close()
