#这个文件专门用来搞确认令牌 登录人的身份 需要连接HTTP和数据库
# 是 客户端 发 token 回来 时候才用到的 所以不写在security里
#security只负责底层验证密码啥的

from sqlalchemy import select
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

import models
from database import get_db
from security import JWT_ALGORITHM, JWT_SECRET_KEY

bearer_reader = HTTPBearer()
#按默认配置，创建一个 HTTPBearer 实例
#只不过是一次带规则的字符串切分。返回一个pydantic类实例
#但携带完整类方法。




# 客户端发来：
# Authorization: Bearer <JWT>

# bearer_reader：
# 识别 Bearer 标记
# → 从请求头中切出真正的 JWT

# jwt.decode：
# 用服务器密钥验签
# → 检查算法
# → 检查过期时间
# → 解出 payload

# 读取 payload["sub"]：
# 得到 user.id
# → 去数据库查 User
# → 查到就放行
# → 任一步不对就返回 401
def get_current_user(
    auth_credentials: HTTPAuthorizationCredentials = Depends(
        bearer_reader
    ),
    #将来有人请求这个接口时，请先找bearer_scheme实例
    #我期待返回一个HTTPAuthorizationCredentials实例 
    #名字就叫credentials

    db: Session = Depends(get_db),
    #Depends(get_db()) 表示现在必须用 交进去的是调用结果
    #Depends(get_db) 表示有这个函数 有要求再用
) -> models.User:
    #我期待最后返回一个user实例

    credentials_exception = HTTPException(
        status_code=401,#unauthorized 身份都是假的
        detail="身份凭证无效",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )
#提前准备统一错误

    token = auth_credentials.credentials
#整张 JWT通行证字符串 包含三部分 但是编码后的Base64URL编码

    try:
        token_decoded = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={
                "require": ["sub", "exp"],
            },
            #这两个都是我们服务器本地规定的验票规则
            #验证：这份内容是不是服务器签发的，有没有被修改。
            #按着这个规定decode
        )
        #现在是字典了

        user_id_text = token_decoded.get("sub")
        #类似token_decoded["sub"] 总之更牛逼

        if user_id_text is None:
            raise credentials_exception

        user_id = int(user_id_text)

    except (InvalidTokenError, TypeError, ValueError):
        raise credentials_exception

    user = db.get(
        models.User,
        user_id,
    )

    if user is None:
        raise credentials_exception

    return user


def get_current_member(current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
) :
    current_member = db.scalar(
        select(models.PartyMember).where(
            models.PartyMember.user_id == current_user.id
        )
    )

    if current_member is None:
        raise HTTPException(
            status_code=403,
            detail="当前用户不在小队中",
        )#Token有效，身份是真的
    return current_member


def require_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,#403 Forbidden  
            #身份是真的，但没资格办这件事
            detail="需要管理员权限",
        )

    return current_user


#依赖链：
# 客户发POST /parties/8/membersAuthorization: Bearer eyJ...
#1.bearer_reader 拆出jwt
#2.get_current_user 拆出jwt手上的sub 拿user
#3.get_current_member 拿member
#4.require_party_leader 拿某队队长
#5._leader_member 真正路由里干活用的 有这个就说明之前都过
def require_leader(
    party_id: int,
    #这个fastapi自动帮你从路由路径里找 
    #那里第一次出现请求的party_id
    current_member: models.PartyMember = Depends(get_current_member),
) -> models.PartyMember:
    if not current_member.is_leader:
        raise HTTPException(
            status_code=403,#403 Forbidden  
            #身份是真的，但没资格办这件事
            detail="需要队长权限",
        )

    if current_member.party_id != party_id:
        raise HTTPException(
            status_code=403,
            detail="不是这个小队",
        )
    return current_member


def require_leader_or_admin(
    party_id: int,
    current_user: models.User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> models.User:
    if current_user.is_admin:
        return current_user

    current_member = db.scalar(
        select(models.PartyMember).where(
            models.PartyMember.user_id
            == current_user.id,
            models.PartyMember.party_id
            == party_id,
        )
    )

    if (
        current_member is None
        or not current_member.is_leader
    ):
        raise HTTPException(
            status_code=403,
            detail="需要本队队长或管理员权限",
        )

    return current_user