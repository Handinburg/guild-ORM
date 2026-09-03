from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas

from database import get_db
from security import hash_password, verify_password,create_access_token
from auth import get_current_user,require_admin
from guild_policy.executor import check_user_registration_policy



router = APIRouter(
    tags=["users"],
)


@router.post(
    "/users/register",
    response_model=schemas.UserResponse,
    status_code=201,
)
def register_user(
    user_data: schemas.UserRegister = Depends(
    check_user_registration_policy
    ),
    #这句 既接受了用户发的 又完成政策校验
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


@router.get(
    "/users",
    response_model=list[schemas.UserResponse],
)
def get_users(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
    limit: int = 20,
    offset: int = 0,
):
    statement = (
            select(models.User)
            .order_by(models.User.id)
            .offset(offset)
            .limit(limit)
        )
    
    user_list = db.scalars(statement).all()
    
    return user_list


@router.get(
    "/users/{user_id}",
    response_model=schemas.UserResponse,
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin : models.User = Depends(require_admin)
):
    user = db.get(
        models.User,
        user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=404,#not found
            detail="用户不存在",
        )

    return user

@router.patch(
    "/users/{user_id}/rank",
    response_model=schemas.UserResponse,
)
def update_user_rank(
    user_id: int,
    rank_data: schemas.UserRankUpdate,
    #拿右
    db: Session = Depends(get_db),
    _admin_user: models.User = Depends(require_admin),
):
    #拿左
    user = db.get(
        models.User,
        user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="用户不存在",
        )
    #业务
    user.adventurer_rank = (
        rank_data.adventurer_rank.value
    )

    db.commit()
    db.refresh(user)

    return user


@router.get(
    "/users/me/party",
    response_model=schemas.PartyResponse,
)
def get_my_party(
    current_user: models.User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    current_member = db.scalar(
        select(models.PartyMember).where(
            models.PartyMember.user_id
            == current_user.id
        )
    )

    if current_member is None:
        raise HTTPException(
            status_code=404,
            detail="当前用户没有加入小队",
        )

    return current_member.party


@router.get(
    "/users/me/quests/alive",
    response_model=list[schemas.QuestResponse],
)
def get_my_alive_quests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alive_status_values = [
        status.value
        for status in models.QUEST_ALIVE_STATUSES
    ]

    statement = (
        #我要quest
        select(models.Quest)
        #粗筛 为了使用current_user
        .join(
            models.Participation,
            models.Participation.quest_id == models.Quest.id,
        )
        .join(
            models.PartyMember,
            models.PartyMember.party_id
            == models.Participation.party_id,
        )
        #细筛 真正业务 什么样的quest
        .where(
            models.PartyMember.user_id == current_user.id,
            models.Quest.status.in_(alive_status_values),
        )
    )

    return db.scalars(statement).all()



#filters
# 1. status=recruiting 
# 2. not in my participation
# 3. minimum rank <= my rank
@router.get(
    "/users/me/quests/available",
    response_model=list[schemas.QuestResponse],
)
def get_my_available_quests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. 找到当前用户所属的小队
    current_member = db.scalar(
        select(models.PartyMember).where(
            models.PartyMember.user_id == current_user.id
        )
    )

    if current_member is None:
        raise HTTPException(
            status_code=404,
            detail="当前用户没有加入小队",
        )

    party = current_member.party

    # 2. 计算小队当前最高等级
    party_rank = party.calculate_party_rank()

    party_rank_position = models.ADVENTURER_RANK_ORDER[
        models.AdventurerRank(party_rank)
    ]

    # 3. 找出这个小队已经接取过的任务ID
    participated_quest_ids = db.scalars(
        select(models.Participation.quest_id).where(
            models.Participation.party_id == party.id
        )
    ).all()

    # 4. 先查询所有正在招募的任务
    statement = select(models.Quest).where(
        models.Quest.status
        == models.QuestStatus.RECRUITING.value
    )

    # 5. 排除本小队已经接取的任务
    if participated_quest_ids:
        statement = statement.where(
            models.Quest.id.not_in(
                participated_quest_ids
            )
        )

    recruiting_quests = db.scalars(statement).all()

    # 6. 只保留小队等级足够的任务
    available_quests = []

    for quest in recruiting_quests:
        minimum_rank_position = (
            models.ADVENTURER_RANK_ORDER[
                models.AdventurerRank(
                    quest.minimum_rank
                )
            ]
        )

        if party_rank_position >= minimum_rank_position:
            available_quests.append(quest)

    return available_quests

@router.delete(
    "/users/{user_id}",
    status_code=204,#204 no content
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):  
    user = db. get(models.User,
                    user_id,
                )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="用户不存在",
        )

    db.delete(user)
    db.commit()
