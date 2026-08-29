from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from security import hash_password, verify_password,create_access_token
from auth import get_current_user


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
    response_model=schemas.TokenResponse,
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
    #拿到db里用户声称的那个username

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
        #直接调用 包装好的verify（security.py文件里）
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
        )
    access_token = create_access_token(user.id)

    return {
    "access_token": access_token,
    #左键 右变量
    "token_type": "bearer",
    #这句写法是标准协议 虽没有执法权但别的应用都这么写
    # 谁携带这张有效通行证，服务器就按通行证中的身份处理请求。
}

@router.get(
    "/users/me",
    response_model=schemas.UserResponse,
)
def get_my_user(
    current_user: models.User = Depends(
        get_current_user
        #我要一个current_user 是User实例 你去调用getxxx函数
        #→ get_current_user验证Token并查询数据库
        #→ 得到models.User实例
        #→ 塞进current_user
    ),
):
    return current_user
