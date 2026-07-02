from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
router = APIRouter(prefix="/api/v1")



@router.get("/")
async def check_endpoint():
    return "aaaaaaa"

__all_routers: list[APIRouter] = [router]


async def startapp(app: FastAPI):
    if __all_routers:
        [app.include_router(router) for router in __all_routers]
    
    
async def shutdown (app: FastAPI):
    ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await startapp(app)
        yield
    finally:
        await shutdown (app)