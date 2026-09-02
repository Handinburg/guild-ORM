from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import require_leader
from guild_policy.executor import check_accept_quest_policy



router = APIRouter(
    tags=["participations"],
)

#队长用 小队接任务
@router.post(
    "/parties/{party_id}/quests/{quest_id}",
    response_model=schemas.ParticipationResponse,
    status_code=201,
)
def accept_quest(
    party_id: int,
    quest_id: int,
    db: Session = Depends(get_db),
    _leader = Depends(require_leader),
    _policy: None = Depends(check_accept_quest_policy)
):
    party = db.get(models.Party, party_id)
    #有这队？
    if party is None:
        raise HTTPException(
            status_code=404,
            detail="小队不存在",
        )

    quest = db.get(models.Quest, quest_id)
    #有着任务？
    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )
    #你重复接取了吗？
    existing_participation = db.scalar(
    select(models.Participation).where(
        models.Participation.party_id == party_id,
        models.Participation.quest_id == quest_id,
    )
)

    if existing_participation is not None:
        raise HTTPException(
            status_code=409,
            detail="该小队已经接受过此任务",
        )

    #status？
    quest_status = models.QuestStatus(quest.status)
    #字符串→ Enum 实例 
    #quest.status：从数据库里拿出来的str 所以需要转换

    if (
        quest_status
        != models.QuestStatus.RECRUITING
    ):
        raise HTTPException(
            status_code=409,
            detail="该任务当前不能接取",
        )

    #检测等级
    party_rank = party.calculate_party_rank()

    if party_rank is None:
        raise HTTPException(
            status_code=409,
            detail="空小队不能接取任务",
        )

    minimum_rank = models.AdventurerRank(
        quest.minimum_rank
    )

    party_rank_position = (
        models.ADVENTURER_RANK_ORDER[
            party_rank
        ]
    )

    minimum_rank_position = (
        models.ADVENTURER_RANK_ORDER[
            minimum_rank
        ]
    )

    if party_rank_position < minimum_rank_position:
        raise HTTPException(
            status_code=403,
            detail="小队等级不足，无法接取该任务",
        )

#业务
#创建类实例
    participation = models.Participation(
        party_id=party_id,
        quest_id=quest_id,
    )

    db.add(participation)
    db.commit()
    db.refresh(participation)

    return participation


#拿着小队找任务
@router.get(
    "/parties/{party_id}/quests",
    response_model=list[schemas.QuestResponse],
)
def get_party_quests(
    party_id: int,
    db: Session = Depends(get_db),
):
    party = db.get(models.Party, party_id)

    if party is None:
        raise HTTPException(
            status_code=404,
            detail="小队不存在",
        )

    quest_list = db.scalars(
        select(models.Quest)
        .join(
            models.Participation,
            models.Participation.quest_id
            == models.Quest.id,
        )
        .where(
            models.Participation.party_id == party_id,
        )
    ).all()
#SELECT quests.*
# FROM quests
# JOIN participations
#     ON participations.quest_id = quests.id
# WHERE participations.party_id = ?;
    return quest_list


#拿着任务找小队
@router.get(
    "/quests/{quest_id}/parties",
    response_model=list[schemas.PartyResponse],
)
def get_quest_parties(
    quest_id: int,
    db: Session = Depends(get_db),
):
    quest = db.get(models.Quest, quest_id)

    if quest is None:
        raise HTTPException(
            status_code= 404,
            detail= "no such quest"
        )

    party_list = db.scalars(
        select(models.Party)
        .join(
            models.Participation,
            models.Participation.party_id
            == models.Party.id,
        )
        .where(
            models.Participation.quest_id == quest_id,
        )
    ).all()

    return party_list


#withdraw from quest
@router.delete(
    "/parties/{party_id}/quests/{quest_id}",
    status_code=204,
)
def withdraw_from_quest(
    party_id: int,
    quest_id: int,
    db: Session = Depends(get_db),
    _leader = Depends(require_leader),
):
    quest = db.get(models.Quest, quest_id)
    #quest ect'?
    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )
    #parici ect'?
    participation = db.scalars(
        select(models.Participation).where(
            models.Participation.party_id == party_id,
            models.Participation.quest_id == quest_id,
        )
    ).first()

    if participation is None:
        raise HTTPException(
            status_code=404,
            detail="该小队没有参与此任务",
        )

    #quest zhit'?
    quest_status = models.QuestStatus(quest.status)

    if quest_status in models.QUEST_DEAD_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="已经结束的任务不能退出",
        )

    #rabotat'
    db.delete(participation)

    db.commit()
