from typing import Annotated

from fastapi import Depends, Request
from app.src.base.config import _GLOBAL_DATABASE_MANAGER
from app.src.dal.main import DataManager


def get_data_manager(request: Request) -> DataManager:
    """
    Доставляет data_manager из `request.app.state`, созданного в lifespan.

    Аргументы:
        request (Request): Объект HTTP-запроса FastAPI.

    Возвращает:
        DataManager: Один и тот же экземпляр, созданный при старте приложения.

    Возможные исключения:
        RuntimeError: Если `data_manager` не инициализирован.
    """
    # 1. Попытка получить из state (предпочтительно, если есть request)
    if request:
        db_manager: DataManager | None = getattr(request.app.state, "data_manager", None)
        if db_manager:
            return db_manager

    # 2. Если request нет или в state ничего нет, берем из ContextVar
    db_manager = _GLOBAL_DATABASE_MANAGER.get()
    if db_manager is None:
        raise RuntimeError(
            "DataManager не инициализирован. Убедитесь, что lifespan приложения (startapp) успешно выполнил инициализацию БД."
        )

    return db_manager


# Alias для аннотаций
DependsDataManager = Annotated[DataManager, Depends(get_data_manager)]


