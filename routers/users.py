from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from security import hash_password, verify_password

router = APIRouter(
    tags=["users"],
)


@router.post(
    "/users/register",
    response_model=schemas.UserResponse,
    status_code=201,
)
def register_user(
    user_data: schemas.UserRegister,
    db: Session = Depends(get_db),
):
    existing_user = db.scalar(
        select(models.User).where(
            models.User.username == user_data.username
        )
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="用户名已存在",
        )

    user = models.User(
        username=user_data.username,
        adventurer_name=user_data.adventurer_name,
        password_hash=hash_password(
            user_data.password
        ),
        is_admin=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

@router.post(
    "/users/login",
    response_model=schemas.UserResponse,
)
def login_user(
    login_data: schemas.UserLogin,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(models.User).where(
            models.User.username == login_data.username
        )
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            # Unauthorized
            detail="用户名或密码错误",
        )

    if not verify_password(
        login_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
        )

    return user