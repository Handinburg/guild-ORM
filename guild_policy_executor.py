# → 使用当前政策检查业务
# → 计算奖励、等级、任务限制

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import models
import schemas

from database import get_db
from guild_policy_loader import (
    GuildPolicy,
    get_current_policy,
)

def check_accept_quest_policy(
    party_id: int,
    db: Session = Depends(get_db),
    current_policy: GuildPolicy = Depends(
        get_current_policy
    ),
) -> None:
    #找左
    active_quest_count = db.scalar(
        select(
            func.count(
                models.Participation.id
            )
        )
        .select_from(
            models.Participation
        )
        .join(
            models.Quest,
            models.Participation.quest_id
            == models.Quest.id,
        )
        .where(
            models.Participation.party_id
            == party_id,
            models.Quest.status
            == "accepted",
        )
    )
    #找右
    maximum_active_quests = (
        current_policy
        .quest
        .max_active_per_party
    )
    #业务
    if (
        active_quest_count is not None and
        active_quest_count >= maximum_active_quests
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "小队同时接取的任务"
                f"不能超过{maximum_active_quests}个"
            ),
        )

def check_user_registration_policy(
    user_data: schemas.UserRegister,
    current_policy: GuildPolicy = Depends(get_current_policy),
) -> schemas.UserRegister:
    #找左
    username = user_data.username
    adventurer_name = user_data.adventurer_name

    #找右
    max_username_length = current_policy.user.max_username_length
    max_adventurer_name_length = current_policy.user.max_adventurer_name_length

    #业务
    if len(username) > max_username_length:
        raise HTTPException(
            status_code=400,
            detail =
                "用户名过长"
                f"不能超过{max_username_length}个字"
        )

    if len(adventurer_name) > max_adventurer_name_length:
        raise HTTPException(
            status_code= 400,
            detail=
                "冒险者名过长"
                f"不能超过{max_adventurer_name_length}个字"
        )
    if (any(character.isspace() for character in username) 
        or any(character.isspace() for character in adventurer_name)
    ):
        raise HTTPException(
            status_code=400,
            detail="用户名或冒险者名不能包含空白字符",
        )

    normalized_username = username.casefold()
    normalized_adventurer_name = adventurer_name.casefold()

    for forbidden_part in current_policy.user.forbidden_name_parts:
        normalized_forbidden_part = forbidden_part.strip().casefold()
        #防止空禁止名""杀掉所有请求

        if (
            normalized_forbidden_part
            and normalized_forbidden_part in normalized_username
        ):
            raise HTTPException(
                status_code=400,
                detail="用户名包含禁止使用的内容",
            )

        if (
            normalized_forbidden_part
            and normalized_forbidden_part in normalized_adventurer_name
        ):
            raise HTTPException(
                status_code=400,
                detail="冒险者名包含禁止使用的内容",
            )
            
    return user_data



def check_party_creation_policy(
    party_data: schemas.PartyCreate,
    current_policy: GuildPolicy = Depends(get_current_policy),
) -> schemas.PartyCreate:
    party_name = party_data.name

    if len(party_name) > current_policy.party.max_name_length:
        raise HTTPException(
            status_code=400,
            detail="队伍名过长",
        )

    if any(character.isspace() for character in party_name):
        raise HTTPException(
            status_code=400,
            detail="不能包含空白字符",
        )

    normalized_partyname = party_name.casefold()

    for forbidden_part in current_policy.party.forbidden_name_parts:
        normalized_forbidden_part = forbidden_part.strip().casefold()
                #防止空禁止名""杀掉所有请求
        if normalized_forbidden_part in normalized_partyname:
            raise HTTPException(
                status_code=400,
                detail="包含禁止使用的内容",
            )

    return party_data