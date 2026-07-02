from fastapi import FastAPI
from .lifespan import lifespan
from .config import uvicorn_config
import uvicorn


def create_app() -> FastAPI:

    swagger_ui_parameters = {
            "syntaxHighlight.theme": "arta",  # Популярная тёмная тема: "arta", "obsidian", "dracula", "monokai"
        }

    app = FastAPI(
            title="Buisenss Manage App",
            description="Сервис управления бизнес-процессами",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            lifespan=lifespan,
            swagger_ui_parameters=swagger_ui_parameters,
        )
    return app


MAIN_APP = create_app()

def main():
    uvicorn.run("app.src.base.main:MAIN_APP", **uvicorn_config.model_dump())
    
if __name__ == "__main__":
    main()


    
