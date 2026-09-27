from sqlalchemy import select

import first_admin
import models
from tests.helpers import TestSessionLocal, create_user


def run_first_admin(monkeypatch, username):
    monkeypatch.setattr(first_admin, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr("builtins.input", lambda _prompt: username)

    first_admin.main()


def test_first_admin_does_not_create_a_missing_user(monkeypatch, capsys):
    run_first_admin(monkeypatch, "missing_user")

    db = TestSessionLocal()
    assert db.scalar(select(models.User)) is None
    db.close()
    assert "用户不存在" in capsys.readouterr().out


def test_first_admin_promotes_only_the_selected_existing_user(monkeypatch, capsys):
    db = TestSessionLocal()
    selected_user = create_user(
        db,
        username="firstboss",
        password_hash="existing_password_hash",
    )
    other_user = create_user(db, username="ordinaryuser")
    selected_user_id = selected_user.id
    other_user_id = other_user.id
    db.close()

    run_first_admin(monkeypatch, "firstboss")

    db = TestSessionLocal()
    stored_selected_user = db.get(models.User, selected_user_id)
    stored_other_user = db.get(models.User, other_user_id)

    assert stored_selected_user is not None
    assert stored_selected_user.is_admin is True
    assert stored_selected_user.password_hash == "existing_password_hash"
    assert stored_other_user is not None
    assert stored_other_user.is_admin is False
    db.close()
    assert "firstboss" in capsys.readouterr().out


def test_first_admin_is_safe_to_repeat_for_an_admin(monkeypatch, capsys):
    db = TestSessionLocal()
    admin = create_user(db, username="existingboss", is_admin=True)
    admin_id = admin.id
    db.close()

    run_first_admin(monkeypatch, "existingboss")

    db = TestSessionLocal()
    stored_admin = db.get(models.User, admin_id)
    assert stored_admin is not None
    assert stored_admin.is_admin is True
    db.close()
    assert "已经是管理员" in capsys.readouterr().out
