# app/src/api/routes/teams.py
"""
Эндпоинты управления командами (Teams).

Роуты:
    GET /teams/{team_id} — получение команды с кэшированием (10 минут)
    POST /teams — создание команды (без кэша)
    GET /teams — получение всех команд (с пагинацией и кэшированием)

Правила:
    - Для чтения используем `CachedUnitOfWork` с TTL.
    - Для записи — обычный `UnitOfWork`.
    - Валидация — через исключения из `app.src.exceptions`.
    - Возвращаем только безопасные схемы (TeamSchema).
"""

from datetime import timedelta
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel
from app.src.api.utils.api_utils import DependsDataManager
from app.src.api.exceptions import TeamAlreadyExists
from app.src.api.services.team_service import TeamService
from app.src.api.shems import TeamSchema, TeamUpdateSheme, TeamCreate

from app.src.api.handlers.team_handlers import (
    create_team_handler,
    delete_team_handler,
    get_all_teams_handler,
    get_team_by_id_handler,
    update_team_handler,
)

team_router = APIRouter(prefix="/teams", tags=["Команды"])


@team_router.get(
    "/{team_id}",
    response_model=TeamSchema,
    status_code=status.HTTP_200_OK,
    summary="Получить команду по ID",
    description="Возвращает команду с указанным ID. Данные кэшируются в Redis на 10 минут.",
    responses={
        200: {"description": "Команда найдена"},
        404: {"description": "Команда не найдена"},
    },
)
async def get_team_by_id_api(
    team_id: UUID,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для получения команды по ID.

    Аргументы:
        team_id (UUID): ID команды.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TeamSchema: Данные команды.
    """
    return await get_team_by_id_handler(team_id, data_manager)


@team_router.post(
    "",
    response_model=TeamSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую команду",
    description="Создаёт команду и назначает пользователя менеджером.",
    responses={
        201: {"description": "Команда успешно создана"},
        409: {"description": "Команда с таким названием уже существует"},
        404: {"description": "Менеджер не найден"},
    },
)
async def create_team_api(
    team_data: TeamCreate,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для создания команды.

    Аргументы:
        team_data (TeamCreate): Данные команды.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TeamSchema: Созданная команда.
    """
    return await create_team_handler(team_data, data_manager)


@team_router.get(
    "",
    response_model=list[TeamSchema],
    status_code=status.HTTP_200_OK,
    summary="Получить все команды",
    description="Возвращает список всех команд с пагинацией. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список команд (может быть пустым)"},
    },
)
async def get_all_teams_api(
    data_manager: DependsDataManager,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Количество записей на страницу")] = 10,
):
    """
    API-обёртка для получения списка всех команд.

    Аргументы:
        data_manager (DependsDataManager): Внедрённый менеджер данных.
        page (int): Номер страницы.
        page_size (int): Размер страницы.

    Возвращает:
        List[TeamSchema]: Список команд.
    """
    return await get_all_teams_handler(page, page_size, data_manager)


@team_router.patch(
    "/{team_id}",
    response_model=TeamSchema,
    status_code=status.HTTP_200_OK,
    summary="Частичное обновление команды",
    description="Обновляет название команды. Данные не кэшируются (изменяют состояние).",
    responses={
        200: {"description": "Команда успешно обновлена"},
        404: {"description": "Команда не найдена"},
    },
)
async def update_team_api(
    team_id: UUID,
    team_update: TeamUpdateSheme,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для частичного обновления команды.

    Аргументы:
        team_id (UUID): ID команды.
        team_update (TeamUpdateSheme): Обновляемые данные.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TeamSchema: Обновлённая команда.
    """
    return await update_team_handler(team_id, team_update, data_manager)


@team_router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить команду",
    description="Удаляет команду по ID. Данные не кэшируются (изменяет состояние).",
    responses={
        204: {"description": "Команда удалена"},
        404: {"description": "Команда не найдена"},
    },
)
async def delete_team_api(
    team_id: UUID,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для удаления команды.

    Аргументы:
        team_id (UUID): ID команды.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        None: Пустой ответ со статусом 204.
    """
    return await delete_team_handler(team_id, data_manager)