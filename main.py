from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

import models
import schemas
from database import get_db
from routers import quests

app = FastAPI()
#FastAPI对象 用来保存路由
app.include_router(quests.router)
#注册我们拆出来的quest模块

@app.get("/")
def root():
    return {"message": "继续学这个的人有大病"}

#新建小队 admin用
@app.post(
    "/parties",
    response_model=schemas.PartyResponse,
    status_code=201,
)#201 Created
def create_party(
    party_data: schemas.PartyCreate,
    db: Session = Depends(get_db),
):
    existing_party = db.scalars(
        select(models.Party).where(
            models.Party.name == party_data.name
        )
    ).first()
    #没找到不要紧 返回none就行 别惦记你那个b for循环了

    if existing_party is not None:
        raise HTTPException(
            status_code=409,
            #conflict
            detail="小队名称已存在",
        )

    party = models.Party(
        name=party_data.name
    )
    #创建新party实例 当作行被orm进db

    db.add(party)
    db.commit()
    db.refresh(party)

    return party

#给某个小队加人 队长用
@app.post(
    "/parties/{party_id}/members",
    response_model=schemas.PartyMemberResponse,
    status_code=201,#created
)
def add_party_member(
    party_id: int,
    party_member_data: schemas.PartyMemberCreate,
    db: Session = Depends(get_db),
):
 #1.小队id检查
    party = db.get(
        models.Party,
        party_id,
    )

    if party is None:
        raise HTTPException(
            status_code=404,#notfound
            detail="小队不存在",
        )
#2.人物id检查
    character = db.get(
        models.Character,
        party_member_data.character_id,
    )

    if character is None:
        raise HTTPException(
            status_code=404,
            detail="角色不存在",
        )


    existing_party_member = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.character_id
            == party_member_data.character_id
        )
    ).first()
#4.人物 是否已有小队
    if existing_party_member is not None:
        raise HTTPException(
            status_code=409,
            #409 Conflict
            detail="该角色已经加入小队",
        )
#5.人物 要加入的队伍里 是否已经有队长
    if party_member_data.is_leader:
        existing_leader = db.scalars(
            select(models.PartyMember).where(
                models.PartyMember.party_id == party_id,
                models.PartyMember.is_leader,
            )
        ).first()

        if existing_leader is not None:
            raise HTTPException(
                status_code=409,
                detail="该小队已经有队长",
            )
#总算过完数据清洗
#开始做准备变量 把pydantic检验后的PartyMemberCreate实例塞给类实例
    party_member = models.PartyMember(
        party_id=party_id,
        character_id=party_member_data.character_id,
        is_leader=party_member_data.is_leader,
    )

    db.add(party_member)
    db.commit()
    db.refresh(party_member)

    return party_member

#查询小队
@app.get(
    "/parties/{party_id}",
    response_model=schemas.PartyResponse,
)
def get_party(
    party_id: int,
    db: Session = Depends(get_db),
):
    party = db.get(
        models.Party,
        party_id,
    )

    if party is None:
        raise HTTPException(
            status_code=404,#not found
            detail="小队不存在",
        )

    return party

#查看所有小队
@app.get(
    "/parties",
    response_model=list[schemas.PartyResponse],
)
def get_parties(
    db: Session = Depends(get_db),
):
    statement = (
        select(models.Party)
        .order_by(models.Party.id)
    )

    party_list = db.scalars(statement).all()

    return party_list

#删除某小队里的 某人 队长用 或者用户本人用
@app.delete(
    "/parties/{party_id}/members/{character_id}",
    status_code=204,#204 no content
)
def remove_party_member(
    party_id: int,
    character_id: int,
    db: Session = Depends(get_db),
):
    party_member = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.party_id == party_id,
            models.PartyMember.character_id == character_id,
        )
    ).first()

    if party_member is None:
        raise HTTPException(
            status_code=404,
            detail="该角色不在此小队中",
        )

    db.delete(party_member)
    db.commit()

#队长用 删除某小队
@app.delete(
    "/parties/{party_id}",
    status_code=204,#204 no content
)
def delete_party(
    party_id: int,
    db: Session = Depends(get_db),
):  
    party = db. get(models.Party,
                    party_id,
                )

    if party is None:
        raise HTTPException(
            status_code=404,
            detail="小队不存在",
        )

    db.delete(party)
    db.commit()

#换队长
@app.patch(
    "/parties/{party_id}/leader",
    response_model=schemas.PartyResponse,
)
def change_party_leader(
    party_id: int,
    leader_data: schemas.LeaderUpdate,
    db: Session = Depends(get_db),
):
    party = db.get(
        models.Party,
        party_id,
    )

    if party is None:
        raise HTTPException(
            status_code=404,
            detail="小队不存在",
        )

    new_leader_party_member = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.party_id == party_id,
            models.PartyMember.character_id
            == leader_data.character_id,
        )
    ).first()

    if new_leader_party_member is None:
        raise HTTPException(
            status_code=404,
            detail="新队长不是该小队成员",
        )

    old_leader_party_member = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.party_id == party_id,
            models.PartyMember.is_leader,
        )
    ).first()

    if old_leader_party_member is not None:
        if new_leader_party_member.id == old_leader_party_member.id:
                raise HTTPException(
                    status_code=409,
                    detail="无效修改,此人已是队长"
                )
        old_leader_party_member.is_leader = False
    new_leader_party_member.is_leader = True
    #为什么写外面 因为就算之前没有队长 （old返回none） 
    # 我们也可以设置新队长

    db.commit()
    db.refresh(party)

    return party


#队长用 小队接任务
@app.post(
    "/parties/{party_id}/quests/{quest_id}",
    response_model=schemas.ParticipationResponse,
    status_code=201,
)
def accept_quest(
    party_id: int,
    quest_id: int,
    db: Session = Depends(get_db),
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

    existing_participation_list = db.scalars(
        select(models.Participation).where(
            models.Participation.party_id == party_id,
        )
    ).all()

    #此为外界规则 需要解耦
    if len(existing_participation_list) >= 3:
        raise HTTPException(
            status_code=409,
            detail="每个小队不得接受超过3个任务",
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
@app.get(
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
@app.get(
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

#admin用 手动改任务status
@app.patch(
    "/quests/{quest_id}/status",
    response_model=schemas.QuestResponse,
)
def update_quest_status(
    quest_id: int,
    status_data: schemas.QuestStatusUpdate,
    db: Session = Depends(get_db),
):
    quest = db.get(models.Quest, quest_id)

    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )

    allowed_status_set = {
        "open",
        "commenced",
        "finished",
        "failed",
        "canceled",
    }

    if status_data.status not in allowed_status_set:
        raise HTTPException(
            status_code=400,
            detail=(
                "请重新规范输入status 参考管理员手册",
            ),
        )

    quest.status = status_data.status

    db.commit()
    db.refresh(quest)

    return quest

#我不干了接口
@app.delete(
    "/parties/{party_id}/quests/{quest_id}",
    status_code=204,
)
def withdraw_from_quest(
    party_id: int,
    quest_id: int,
    db: Session = Depends(get_db),
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