from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db


router = APIRouter(
    tags=["parties"],
)

#新建小队 admin用
@router.post(
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
@router.post(
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
@router.get(
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
@router.get(
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
@router.delete(
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
@router.delete(
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
@router.patch(
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