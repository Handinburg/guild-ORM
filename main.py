from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

import models
import schemas
from database import get_db
from routers import quests,parties,participations

app = FastAPI()
#FastAPI对象 用来保存路由
app.include_router(quests.router)
#注册我们拆出来的quest模块
app.include_router(parties.router)
app.include_router(participations.router)

@app.get("/")
def root():
    return {"message": "继续学这个的人有大病"}
