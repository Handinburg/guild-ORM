# → 定义GuildPolicy模型
# → 读取和校验JSON
# → 提供get_current_policy()
import json
from pathlib import Path

from pydantic import BaseModel, Field


class QuestPolicy(BaseModel):
    max_active_per_party: int = Field(
        ge=1,
        #工会允许调整任务上限，
        # 但不能制定“任何小队一个任务都不准接”的非法政策。
    )

class PartyPolicy(BaseModel):
    max_name_length : int = Field(
            ge=1,
        )
    #0 → 只能同级组队
    #1 → 最低和最高最多差一级
    #2 → 最多差两级
    max_rank_gap: int = Field(
        ge=0,
    )
    forbidden_name_parts :list

class UserPolicy(BaseModel):
    max_username_length : int = Field(
        ge=1,
    )
    max_adventurer_name_length : int = Field(
        ge=1,
    )
    forbidden_name_parts :list

class GuildPolicy(BaseModel):
    quest: QuestPolicy
    party: PartyPolicy
    user: UserPolicy


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
        #把这份普通字典交给 GuildPolicy 类检查，
        # 并制造一个符合要求的 GuildPolicy 实例
        #→ GuildPolicy
    )


CURRENT_POLICY = load_guild_policy()
#只在模块首次导入时执行一次。
# 因此修改 JSON 后，要重启程序，才会重新加载政策。

def get_current_policy() -> GuildPolicy:
    return CURRENT_POLICY