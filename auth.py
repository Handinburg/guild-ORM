#这个文件专门用来搞确认令牌 登录人的身份 需要连接HTTP和数据库
# 是 客户端 发 token 回来 时候才用到的 所以不写在security里
#security只负责底层验证密码啥的

#工作流：
# 读取Authorization请求头
# → 取出JWT
# → 解码
# → 取得user.id
# → 查询数据库
# → 返回models.User
# → 失败时返回HTTP 401

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

#credentials.credentials
# "eyJ..."


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
        status_code=401,
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
