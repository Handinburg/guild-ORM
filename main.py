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




