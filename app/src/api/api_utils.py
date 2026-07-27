
"""
Утилиты для доставки зависимостей в FastAPI-эндпоинтах.

Используется для передачи объектов, созданных в lifespan (например, data_manager).
"""

from typing import Annotated
from fastapi import Depends, Request
from app.src.dal.main import DataManager


def get_data_manager(request: Request) -> DataManager:
    """
    Доставляет data_manager из `request.app.state`, созданного в lifespan.

    Аргументы:
        request (Request): Объект HTTP-запроса FastAPI.

    Возвращает:
        DataManager: Один и тот же экземпляр, созданный при старте приложения.

    Возможные исключения:
        AttributeError: Если `request.app.state.data_manager` не инициализирован.

    Пример:
        async def get_user(user_id: UUID, data_manager: DependsDataManager):
            async with data_manager() as uow:
                ...
    """
    return request.app.state.data_manager


# Alias для аннотаций
DependsDataManager = Annotated[DataManager, Depends(get_data_manager)]


