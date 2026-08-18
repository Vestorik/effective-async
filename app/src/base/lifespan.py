from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from app.src.api.main import api_routers
from app.src.api.admin.admin import SQLAdminViewSet
from fastapi_swagger_ui_theme import setup_swagger_ui_theme
from app.src.dal.main import get_data_manager
from app.src.base.config import _GLOBAL_DATABASE_MANAGER
from logging import getLogger
logger = getLogger(__name__)

__all_routers: list[APIRouter] = api_routers

async def startapp(app: FastAPI):
    # Инициализация SQLAdmin админ-панели

    if __all_routers:
        [app.include_router(router) for router in __all_routers]

    setup_swagger_ui_theme(
        app,
        docs_path="/docs",
    )
    data_manager = await get_data_manager()
    app.state.data_manager = data_manager
    logger.info("SQL Admin started")
    _GLOBAL_DATABASE_MANAGER.set(data_manager)
    
    SQLAdminViewSet(
        app=app,
        secret_key="change-this-to-a-secure-key-in-production",
        databse_engine=data_manager.database_manager.get_engine,
        db_manager=data_manager
    )


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
