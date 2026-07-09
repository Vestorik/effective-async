from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from app.src.api.handlers import api_router
from fastapi_swagger_ui_theme import setup_swagger_ui_theme


__all_routers: list[APIRouter] = [api_router]


async def startapp(app: FastAPI):
    if __all_routers:
        [app.include_router(router) for router in __all_routers]

    setup_swagger_ui_theme(
        app,
        docs_path="/docs",
    )


async def shutdown(app: FastAPI): ...


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await startapp(app)
        yield
    finally:
        await shutdown(app)
