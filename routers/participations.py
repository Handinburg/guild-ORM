from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import require_leader
from guild_policy_executor import check_accept_quest_policy



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
    _active_quest_limit: None = Depends(check_accept_quest_policy)
):
    party = db.get(models.Party, party_id)

    if party is None:
        raise HTTPException(
            status_code=404,
            detail="小队不存在",
        )

    quest = db.get(models.Quest, quest_id)

    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )

    existing_participation = db.scalars(
        select(models.Participation).where(
            models.Participation.party_id == party_id,
            models.Participation.quest_id == quest_id,
        )
    ).first()

    if existing_participation is not None:
        raise HTTPException(
            status_code=409,
            detail="该小队已经接受过此任务",
        )

    if not quest.is_cooperative:
        other_participation = db.scalars(
            select(models.Participation).where(
                models.Participation.quest_id == quest_id,
            )
        ).first()

        if other_participation is not None:
            raise HTTPException(
                status_code=409,
                detail="该任务已经被其他小队接受",
            )

    if quest.status != "open":
        raise HTTPException(
            status_code=409,
            detail="该任务目前不开放",
        )

#别看花眼 这个是创建类实例
    participation = models.Participation(
        party_id=party_id,
        quest_id=quest_id,
    )

    db.add(participation)

    if not quest.is_cooperative:
        quest.status = "commenced"

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


#我不干了接口
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

    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )

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

    if quest.status not in {
        "open",
        "commenced",
    }:
        raise HTTPException(
            status_code=409,
            detail="已经结束的任务不能退出",
        )

    other_participation = db.scalars(
        select(models.Participation).where(
            models.Participation.quest_id == quest_id,
            models.Participation.party_id != party_id,
        )
    ).first()

    db.delete(participation)

    if other_participation is None:
        quest.status = "open"

    db.commit()