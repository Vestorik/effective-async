from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from app.src.api.main import api_routers
from app.src.api.admin import admin_view_set
from fastapi_swagger_ui_theme import setup_swagger_ui_theme
from app.src.dal.main import get_data_manager


__all_routers: list[APIRouter] = api_routers


async def startapp(app: FastAPI):
    # Инициализация SQLAdmin админ-панели
    admin_view_set.setup(
        app=app,
        secret_key="change-this-to-a-secure-key-in-production",
    )
    app.include_router(admin_view_set.admin.urls)

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

