from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas

from database import get_db
from auth import require_admin,require_leader
from guild_policy.executor import (
    check_party_creation_policy,
    check_party_rank_gap_policy,
    )

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
    party_data: schemas.PartyCreate=Depends(
        check_party_creation_policy),
    #接受数据 并进行政策检验
    db: Session = Depends(get_db),
    _admin_user: models.User = Depends(require_admin),
):
    #检查队长
        #1.有这人？
        #2.这人在其他队？
    leader_user = db.get(
    models.User,
    party_data.leader_user_id,
)

    if leader_user is None:
        raise HTTPException(
            status_code=404,
            detail="初始队长用户不存在",
        )

    existing_member = db.scalar(
    select(models.PartyMember).where(
        models.PartyMember.user_id
        == party_data.leader_user_id
    )
)

    if existing_member is not None:
        raise HTTPException(
            status_code=409,#conflict
            detail="该用户已经加入其他小队",
        )
    
    #检查队伍
        #1.有这名？
    existing_party = db.scalars(
        select(models.Party).where(
            models.Party.name == party_data.name
        )
    ).first()

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
    db.flush()
    #→提前执行INSERT，取得party.id，但不结束事务
    #现在就有生成的主键 party.id了

    first_party_member = models.PartyMember(
    party_id=party.id,
    user_id=party_data.leader_user_id,
    is_leader=True,
    )
    db.add(first_party_member)

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
    _leader = Depends(require_leader),
    party_member_data: schemas.PartyMemberCreate= Depends(
        check_party_rank_gap_policy
    ),
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
#2.用户id检查
    user = db.get(
        models.User,
        party_member_data.user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="用户不存在",
        )


    existing_party_member = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.user_id
            == party_member_data.user_id
        )
    ).first()
#4.用户是否已有小队
    if existing_party_member is not None:
        raise HTTPException(
            status_code=409,
            #409 Conflict
            detail="该用户已经加入小队",
        )
#5.用户要加入的队伍里是否已经有队长
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
        user_id=party_member_data.user_id,
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
    "/parties/{party_id}/members/{user_id}",
    status_code=204,#204 no content
)
def remove_party_member(
    party_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _leader = Depends(require_leader)
):
    party_member = db.scalars(
        select(models.PartyMember).where(
            models.PartyMember.party_id == party_id,
            models.PartyMember.user_id == user_id,
        )
    ).first()

    if party_member is None:
        raise HTTPException(
            status_code=404,
            detail="该用户不在此小队中",
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
    _leader = Depends(require_leader),
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
    _leader = Depends(require_leader),
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
            models.PartyMember.user_id
            == leader_data.user_id,
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
