# → 定义GuildPolicy模型
# → 读取和校验JSON
# → 提供get_current_policy()
import json
from pathlib import Path

from pydantic import BaseModel, Field


class QuestPolicy(BaseModel):
    max_active_per_party: int = Field(
        ge=1,
    )

class PartyPolicy(BaseModel):
    pass

class GuildPolicy(BaseModel):
    quest: QuestPolicy
    party: PartyPolicy


POLICY_FILE = Path(__file__).with_name(
    "guild_policy.json"
)


def load_guild_policy() -> GuildPolicy:
    with POLICY_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        policy_data = json.load(file)
        #→ 普通Python字典

    return GuildPolicy.model_validate(
        policy_data
        #→ GuildPolicy对象
    )


CURRENT_POLICY = load_guild_policy()


def get_current_policy() -> GuildPolicy:
    return CURRENT_POLICY