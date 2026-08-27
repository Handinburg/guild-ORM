from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

import models
import schemas
from database import get_db
from routers import quests,parties,participations,users

app = FastAPI()
#FastAPI对象 用来保存路由
app.include_router(quests.router)
#注册我们拆出来的quest模块,below same
app.include_router(parties.router)
app.include_router(participations.router)
app.include_router(users.router)



@app.get("/")
def root():
    return {"message": "继续学这个的人有大病"}


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from security import hash_password


router = APIRouter(
    tags=["users"],
)


@router.post(
    "/users/register",
    response_model=schemas.UserResponse,
    status_code=201,
)
def register_user(
    user_data: schemas.UserRegister,
    db: Session = Depends(get_db),
):
    existing_username = db.scalar(
        select(models.User).where(
            models.User.username == user_data.username
        )
    )

    if existing_username is not None:
        raise HTTPException(
            status_code=409,
            detail="用户名已存在",
        )
    
    user = models.User(
    username=user_data.username,
    adventurer_name=user_data.adventurer_name,
    password_hash=hash_password(user_data.password),
    is_admin=False,
)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user