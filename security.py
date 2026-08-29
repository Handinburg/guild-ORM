#底层安全工具
#不认识HTTP和数据库
#战略思想：不能让明文密码存在数据库里 只能在内存里暂时闪现一下
from pwdlib import PasswordHash
#→ pwdlib提供的一个类，专门负责生成和验证密码哈希

import os
from datetime import datetime, timedelta, timezone

import jwt

password_hasher = PasswordHash.recommended()
#→ 给我一台配置好的密码处理机器
#把这台“密码处理机器”保存到变量 password_hash 里，后面反复使用

#注册时使用：
def hash_password(password: str) -> str:
    #我要一个字符串形式的明文密码
    #->表示函数最终返回一个字符串。这个字符串不再是明文密码，而是一长串密码哈希，
    #这玩意和：一样 也只是注释而已 没有执法权
    return password_hasher.hash(password)
#调用密码机的.hash（）方法处理输入的明文密码，输出这个 额游击队密码
#标准叫法：密码哈希值。无法被解码
#到时候数据库里就存这个哈希值


JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "development-secret-change-before-deploy",
)

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 30
#jwt外挂配置 准备好算法 印章 时间


#登录尝试时使用：
def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    #我要你尝试输入的明文密码
    #和数据库里的 密码哈希值
    return password_hasher.verify(
        plain_password,#这个是用户的真密码
        hashed_password,#这个是数据库里的hash
    )
#调用密码机的 verify() 方法
#从旧哈希里挖出当年的盐，复刻当年的工序。
#如果相同，verify() 返回：True

#某一行的结构为：
#id=17
#username=Arthur
#password_hash=算法参数 + 当年设置密码时的盐AAA + 哈希结果XXX
#改密码时同一行、同一个主键，会换成包含新盐的新 password_hash。

#盐的作用就一句话：
#让相同的密码也产生不同的哈希，阻止攻击者批量复用提前算好的破解结果。


def create_access_token(user_id: int) -> str:
    expire_time = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    token = {
        "sub": str(user_id),
        #JWT规范把 sub 当字符串，所以即使主键是整数，也先转str
        "exp": expire_time,
    }
    #现在是字典

    return jwt.encode(
        token,
        JWT_SECRET_KEY,
        #是服务器盖章使用的秘密。
        algorithm=JWT_ALGORITHM,
    )
    #现在是经过编码并签名的 Token；payload 可以被读取，不是加密内容

#"JSON Web Tokens"三段：
    #Header     使用什么签名算法
    #Payload    通行证写了谁、何时过期
    #Signature  服务器盖的防伪章
