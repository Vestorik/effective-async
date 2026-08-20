from fastapi import FastAPI
from .lifespan import lifespan
from .config import uvicorn_config
import uvicorn
from fastapi.middleware.cors import CORSMiddleware 


def create_app() -> FastAPI:


    app = FastAPI(
            title="Buisenss Manage App",
            description="Сервис управления бизнес-процессами",
            version="1.0.0",
            docs_url=None,
            redoc_url="/redoc",
            lifespan=lifespan,
        )
    return app


MAIN_APP = create_app()

MAIN_APP.add_middleware(
    CORSMiddleware
)

def main():
    uvicorn.run("app.src.base.main:MAIN_APP", **uvicorn_config.model_dump())
    
if __name__ == "__main__":
    main()


    
