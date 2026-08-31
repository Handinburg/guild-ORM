from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import require_admin


router = APIRouter(
    tags=["quests"],
)

#创建任务 admin用
@router.post(
    "/quests",
    response_model=schemas.QuestResponse,
    status_code=201,
)
def create_quest(
    # JSON→QuestCreate对象
    quest_data: schemas.QuestCreate,
    db: Session = Depends(get_db),
    _admin_user: models.User = Depends(require_admin),
    #_表示这个参数必须存在，但我故意不在函数体里读取它，
    # 程序员的约定写法。我只需要执行依赖
):

    
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
# @router.get(
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
@router.get(
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

@router.get(
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
@router.patch(
    "/quests/{quest_id}",
    response_model=schemas.QuestResponse,
)
def update_quest(
    quest_id: int,
    #target
    quest_data: schemas.QuestUpdate,
    #payload
    db: Session = Depends(get_db),
    _admin_user: models.User = Depends(require_admin),
    #authorization
):

    #有这任务？
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
    #有这cate？
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
@router.delete(
    "/quests/{quest_id}",
    status_code=204,# No Content
)
def delete_quest(
    quest_id: int,
    db: Session = Depends(get_db),
    _admin_user: models.User = Depends(require_admin),
):
    quest = db.get(models.Quest, quest_id)

    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )

    db.delete(quest)
    db.commit()

    # 创建成功：201 Created + 返回创建后的资源
    # 删除成功：204 No Content + 不返回正文 所以这里不用写response model


#admin用 手动推进status
@router.patch(
    "/quests/{quest_id}/status",
    response_model=schemas.QuestResponse,
)
def update_quest_status(
    quest_id: int,
    status_data: schemas.QuestStatusUpdate,
    db: Session = Depends(get_db),
    _admin_user: models.User = Depends(require_admin),
):
    quest = db.get(models.Quest, quest_id)

    if quest is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在",
        )

    #需解耦 check_allowed_status_set
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
