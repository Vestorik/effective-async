from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from app.src.api.main import api_router
from fastapi_swagger_ui_theme import setup_swagger_ui_theme
from app.src.dal.main import get_data_manager


__all_routers: list[APIRouter] = [api_router]


async def startapp(app: FastAPI):
    if __all_routers:
        [app.include_router(router) for router in __all_routers]

    setup_swagger_ui_theme(
        app,
        docs_path="/docs",
    )
    
    app.state.data_manager = await get_data_manager()


async def shutdown(app: FastAPI): 
    if hasattr(app.state, "data_manager"):
        await app.state.data_manager.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await startapp(app)
        yield
    finally:
        await shutdown(app)


