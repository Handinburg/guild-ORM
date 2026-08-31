# → 使用当前政策检查业务
# → 计算奖励、等级、任务限制

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import models

from database import get_db
from guild_policy_loader import (
    GuildPolicy,
    get_current_policy,
)


def check_active_quest_limit(
    party_id: int,
    db: Session = Depends(get_db),
    current_policy: GuildPolicy = Depends(
        get_current_policy
    ),
) -> None:
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

    maximum_active_quests = (
        current_policy
        .quest
        .max_active_per_party
    )

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