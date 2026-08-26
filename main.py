from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

import models
import schemas
from database import get_db
from routers import quests

app = FastAPI()
#FastAPI对象 用来保存路由

@app.get("/")
def root():
    return {"message": "继续学这个的人有大病"}

#创建任务 admin用
@app.post(
    "/quests",
    response_model=schemas.QuestResponse,
    status_code=201,
)
def create_quest(
    # FastAPI读取请求JSON，
    # Pydantic校验后创建QuestCreate对象
    #1.Pydantic将json变为 QuestCreate 对象 对象名 quest_data 用于校验请求数据
    quest_data: schemas.QuestCreate,

        # FastAPI通过get_db取得SQLAlchemy Session对象db
    db: Session = Depends(get_db),
):
        #  db对象呼出get()方法按照主键查询数据库  这步只是为了防止请求数据库里不存在的类别
         # 语法为db.get(ORM模型, 主键值) 类似SQLAlchemy里的raw sql
    category = db.get(
        models.QuestCategory,
        quest_data.category_id,
    )

                 # category的结果：
                    # 找到    → QuestCategory ORM对象
                    # 找不到  → None
    if category is None:
        raise HTTPException(
            status_code=404,
            detail="任务类别不存在",
        )

#model_dump()把 Pydantic对象转换成普通字典对象data，用于临时传递字段
#quest_data 作为Pydantic对象 自带model_dump()方法
    # {
    #     "title": "清除哥布林",
    #     "description": "村庄附近出现了哥布林",
    #     "completion_criteria": "消灭5只哥布林",
    #     "category_id": 1,
    # }
    data = quest_data.model_dump()

#**data表示 “拆开这个字典，把冒号都换成等号”
# 文艺一点说就是把字典中的“键: 值”展开成“参数名=参数值”。

#models是你自己的文件 草 quest是你model文件里定义的ORM类 难崩，这都给忘了

#Quest()
#类名后加括号，表示创建这个类的一个对象。基础知识 小伙子学艺不精啊
#不用**用字典创建非空对象：
#quest = models.Quest(
    #title="清除哥布林",
    #description="村庄附近出现了哥布林",
    #completion_criteria="消灭5只哥布林",
    #category_id=1,
#)

#综上，Quest(**data)把data字典 高效地 转化成 quest类下实例。

# 转换后，SQLAlchemy知道：这是 Quest 类下实例对象，应该插入 quests 表。这里才是orm
#为什么知道？因为在models里 我写了（md是我自己写的 草）
# class Quest(Base):
    #__tablename__ = "quests"

    quest = models.Quest(**data)

#剩下的就是填表 commit 成为.db里的一行
    db.add(quest)
    db.commit()

#根据 quest 的主键，重新从数据库查询这一行，
# 并用数据库里的最新数据刷新当前 quest 对象。
#数据库插入后，可能补充：
#id = 2
#status = open

    db.refresh(quest)
    #此时仍拿到 quest类

    return quest
    #由于之前写了response_model=QuestResponse
        #→此时 pydantic把 ORM对象 → Pydantic响应格式

#总结 用户json→ pydantic的quest_creat类 →字典（为了一次录入）→ quest类（这里才是ORM）
#  → 录入 → fetch一个quest类例 → pydantic的response类验证 →fastapi处理quest类例 返回json

#SQLAlchemy知道：Quest 类下实例对象，应该插入 quests 表。这里才是orm
#为什么知道？因为在models里 你写了
# class Quest(Base):
    #__tablename__ = "quests" 
    # 建立了 Quest 类 和 quests表 的映射

#查询全部任务 已经被下面带筛选功能的替换了 
# @app.get(
#     "/quests",
#     response_model=list[schemas.QuestResponse],
# )
# def get_quests(
#     db: Session = Depends(get_db),
# ):
#     statement = select(models.Quest)

#     quests = db.scalars(statement).all()

#     return quests

#db相当于conn+cursor 
#quests拿到 list【quest类】 → response_model=list[schemas.QuestResponse] →
# fastapi依次处理列表中的每个 Quest对象返回json

#按序号查任务
@app.get(
    "/quests/{quest_id}",
    response_model=schemas.QuestResponse,
)
def get_quest(
    quest_id: int,
    db: Session = Depends(get_db),
):
    quest = db.get(models.Quest, quest_id)

    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )

    return quest

#注意到def要求传入 quest_id db
#db下get方法 进数据库按id找quest
#quest变量 拿到 quest类orm实例对象（这句话太难崩了）
#response_model 把 quest变量 用QuestResponse规则 验证quest实例对象的属性
#FastAPI把验证后的响应数据转换成JSON返回

@app.get(
    "/quests",
    response_model=list[schemas.QuestResponse],
)
def get_quests(
    status: str | None = None,
    category_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
#要求传入 可选过滤项 状态和 任务类别名
#预设 limit 和 offset 分页 

#准备基础sql prompt
    statement = select(models.Quest)

    #用.where（）增加条件 
    if status is not None:
        statement = statement.where(
            models.Quest.status == status
        )

    #.has（name=讨伐）查询关联类别的 name等于“讨伐”的任务。
        # .has()：查“这个对象关联的那个对象”是否符合条件
        # .any()：查“这个对象关联的一堆对象里”有没有符合条件的
        
        #为什么这么写？ 
        # 因为  models.Quest.category 是 Quest类上的 ORM关系属性，
        # 不是某个具体类别对象。
        #此时还没有查出来任何一个category 不能用models.Quest.category.name
        #如果真查出来一个quest（注意大小写 这是类实例），才能用quest.category.name
    if category_name is not None:
        statement = statement.where(
            models.Quest.category.has(
                name=category_name
            )
        )

    statement = (
        statement
        .order_by(models.Quest.id.desc())
        .offset(offset)
        .limit(limit)
    )

    quests = db.scalars(statement).all()

    return quests

#新知识：.where（）相当于+= 用来给原始全选prompt加限制
    # .has()、.any()：用于整个类里查实例匹配

#QuestUpdate
@app.patch(
    "/quests/{quest_id}",
    response_model=schemas.QuestResponse,
)
def update_quest(
    quest_id: int,
    quest_data: schemas.QuestUpdate,
    db: Session = Depends(get_db),
):
#注意到要求输入 quest_id: int,quest_data: schemas.QuestUpdate,
    #db由Depends(get_db)自动提供
    #db handle呼出.get(models.Quest, quest_id) 按id查表 如未查到返回404
    quest = db.get(models.Quest, quest_id)

    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )

#用quest_data.model_dump(）方法把 Pydantic检测后的json 转换成普通字典对象update_data 
# 方便之后用 .items() + setattr()批量修改。
    update_data = quest_data.model_dump(
        exclude_unset=True
    )
#如果还要改 categoryid的 检测下是否在QuestCategory表里
    if "category_id" in update_data:
        category = db.get(
            models.QuestCategory,
            update_data["category_id"],
        )

        if category is None:
            raise HTTPException(
                status_code=404,
                detail="任务类别不存在",
            )
# 遍历字典中的字段和值。
    for field, value in update_data.items():

 
    #python自带函数：setattr(对象, "属性名", 值)
       # 相当于：
        # quest.title = value
        # quest.description = value
    #用于动态修改对象属性
    #配套的是只读的 getattr（）
        setattr(quest, field, value)

# SQLAlchemy发现quest属性发生变化，
# 自动生成并执行UPDATE，然后提交事务。
    db.commit()
#改，传 拿改后的的quest类实例
#经过pydantic检测
#fastapi转回json 
    db.refresh(quest)
    return quest

#新知识 准备好字典 用 .items()和setattr（对象, "属性名", 值）批量修改字典

#删quest
@app.delete(
    "/quests/{quest_id}",
    status_code=204,
)
def delete_quest(
    quest_id: int,
    db: Session = Depends(get_db),
):
    quest = db.get(models.Quest, quest_id)

    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )

    db.delete(quest)
    db.commit()

#行业惯例： 
    # 创建成功：201 Created + 返回创建后的资源
    # 查询成功：200 OK + 返回资源
    # 更新成功：200 OK + 返回更新后的资源
    # 删除成功：204 No Content + 不返回正文 所以这里不用写response model





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