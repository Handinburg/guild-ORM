from sqlalchemy import select

import models
from database import SessionLocal


def main():
    username = input("请输入要设为管理员的登录用户名：")

    with SessionLocal() as db:
        statement = select(models.User)
        statement = statement.where(
            models.User.username == username
        )

        user = db.scalar(statement)

        if user is None:
            print("用户不存在，请先通过注册接口创建账号。")
            return

        if user.is_admin:
            print("这个用户已经是管理员。")
            return

        user.is_admin = True
        db.commit()

        print(f"已将 {username} 设置为管理员。")

#直接运行就办事，被导入时先不办事。
if __name__ == "__main__":
    main()