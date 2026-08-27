from pydantic import BaseModel, ConfigDict


class QuestCreate(BaseModel):
    title: str
    description: str
    completion_criteria: str
    category_id: int


class QuestResponse(BaseModel):
    id: int
    title: str
    description: str
    completion_criteria: str
    status: str
    category_id: int

    model_config = ConfigDict(from_attributes=True)
    #from_attributes=True允许 Pydantic这样读取：
        # quest.id
        # quest.title
        # quest.status

class QuestUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    completion_criteria: str | None = None
    category_id: int | None = None


class PartyCreate(BaseModel):
    name: str


class PartyMemberCreate(BaseModel):
    user_id: int
    is_leader: bool = False


class UserBriefResponse(BaseModel):
    id: int
    username: str | None
    adventurer_name:str | None
    model_config = ConfigDict(
        from_attributes=True
    )

class PartyMemberResponse(BaseModel):
    id: int
    party_id: int
    user_id: int
    is_leader: bool
    user: UserBriefResponse

    model_config = ConfigDict(
        from_attributes=True
    )


class PartyResponse(BaseModel):
    id: int
    name: str
    member_list: list[PartyMemberResponse]

    model_config = ConfigDict(
        from_attributes=True
    )

class LeaderUpdate(BaseModel):
    user_id: int

class LeaderVerification(BaseModel):
    user_id: int

class ParticipationResponse(BaseModel):
    id: int
    quest_id: int
    party_id: int

    model_config = ConfigDict(
        from_attributes=True,
    )

class QuestStatusUpdate(BaseModel):
    status: str


class UserRegister(BaseModel):
    username: str
    adventurer_name: str
    password: str
    #UserRegister 里故意没有：
    #is_admin: bool

class UserResponse(BaseModel):
    id: int
    username: str
    adventurer_name: str
    is_admin: bool

    model_config = ConfigDict(
        from_attributes=True,
    )

       #UserResponse 故意不包含：
        #password
        #password_hash

class UserLogin(BaseModel):
    username: str
    password: str