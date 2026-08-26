from sqlalchemy import Integer, String,Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column,relationship
class Base(DeclarativeBase):
    pass


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    race: Mapped[str | None] = mapped_column(String)
    level: Mapped[int | None] = mapped_column(Integer)
    country_id: Mapped[int | None] = mapped_column(Integer)
    real_country_id: Mapped[int | None] = mapped_column(Integer)


class QuestCategory(Base):
    __tablename__ = "quest_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)

    quest_list: Mapped[list["Quest"]] = relationship(
        back_populates="category"
    )
   #ForeignKey + relationship
        #→ Quest对象能够找到Category对象
        #→ 允许 quest.category 或 category.quest_list


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    completion_criteria: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")

    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("quest_categories.id"),
    )

    category: Mapped["QuestCategory"] = relationship(
        back_populates="quest_list"
    )

    participation_list : Mapped[list["Participation"]] = relationship(
        back_populates="quest"
    )
    is_cooperative: Mapped[bool] = mapped_column(
        Boolean,
        default= False
    )


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
#左侧：Python/ORM对象
    # id：写法是类属性 在类上声明“以后每个Party实例都有id属性”
    # 因为类上属性，以后可写 Party.id来构造查询
    # Mapped[]：告诉 SQLAlchemy这是一个受 ORM管理的属性
    # int：在 Python里是整数

#右侧：数据库表
    #mapped_column()：定义一个列
    #id不再是普通类属性，是 SQLAlchemy专门的“类上声明、实例上存值”的特殊属性。
    # Integer：在db里是整数

#总结：
    # Party.id：构造查询
    # party.id：读取具体值
    # parties.id：数据库真实列
    name: Mapped[str] = mapped_column(
        String,
        unique=True,
    )
    member_list: Mapped[list["PartyMember"]] = relationship(
    #python这边要一堆PartyMember组成的list
    #relationship() 表示 具体数据咱还得去别的表找，现在这表里没有这列
        #怎么找？自己去找foreigh key！
        #找到后就能写Party.member_list了
        back_populates="party",
            #表示双向关系 两边都写 
            
        cascade="all, delete-orphan",
          #不管
    )   
    participation_list:Mapped[list["Participation"]] = relationship(
        back_populates="party",
        cascade="all, delete-orphan",
    )
    #为什么要双引号participation？ 这叫前向引用
    # 等于告诉 Python/SQLAlchemy：
    # 先把这个名字记下来，等所有类都定义完成以后，再去找 Participation。


class PartyMember(Base):
    __tablename__ = "party_members"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    party_id: Mapped[int] = mapped_column(
        ForeignKey("parties.id"),
        #哟 这不是之前parties表里要我找的foreign key吗 那我直接join了
        #你之前不是要一堆PartyMember的list吗 那还说啥了 给了
    )

    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id"),
        unique=True,
    )

    is_leader: Mapped[bool] = mapped_column(
    Boolean,
    #bool 是pyhton语言 Boolean是数据库语言
    default=False,
)

    party: Mapped["Party"] = relationship(
        back_populates="member_list",
        #由于这对back_populates，之后就能写 partymember.party了
        #一对relationship（back_populates）共用一个外键
    )

    character: Mapped["Character"] = relationship()

class Participation(Base):
    __tablename__ = "participations"
    #多对多中间表来啦

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    quest_id: Mapped[int] = mapped_column(
        ForeignKey("quests.id"),
    )

    party_id: Mapped[int] = mapped_column(
        ForeignKey("parties.id"),
    )

    quest: Mapped["Quest"] = relationship(
        back_populates="participation_list",
    )

    party: Mapped["Party"] = relationship(
        back_populates="participation_list",
    )