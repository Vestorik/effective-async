from fastapi import APIRouter, Query, BackgroundTasks
from email.header import Header
from asyncio import sleep as asleep
from pydantic import BaseModel, Field
from fastapi import Depends
from fastapi.exceptions import HTTPException
from typing import Annotated


api_router = APIRouter()

async def mail(email):
    await asleep(5)
    print(f"{email} получил сообщение")

@api_router.get("/")
async def root():
    return {"message": "Hello World"}


class User(BaseModel):
    name: str = Field(min_length=3)
    age: int = Field(ge=18, le=100)
    email: str

    
@api_router.post('/registry/')
async def registry_handler(user: User, back_task: BackgroundTasks):
    back_task.add_task(mail, user.email)
    return "Пользователь {user.name} успешно зарегестрирован"


def check_token(token: Annotated[str, Header] | None = None, 
                token2: Annotated[str, Query] | None = None) -> str | None:
    base_tocken = "aaa"
    
    current_token = token or token2
    
    if base_tocken == current_token: 
        return token
    raise HTTPException(status_code=403, detail="Токен не действитилен")


@api_router.get('/sicret_data/')
async def sicret_data(tok_valid: str = Depends(check_token)):
    return {"message":"доступ разрешен"}