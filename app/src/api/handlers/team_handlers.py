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
from app.src.api.api_utils import DependsDataManager
from app.src.api.exceptions import TeamAlreadyExists
from app.src.api.services.team_service import TeamService
from app.src.api.shems import TeamSchema, TeamUpdateSheme


team_router = APIRouter(prefix="/teams", tags=["Команды"])


# —————— 1. GET /teams/{team_id} — кэшированная операция — 10 минут ——————

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
async def get_team_by_id(
    team_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Получение команды по ID через кэшированный Unit of Work.

    Использование кэша:
        - `data_manager.cache(timedelta(minutes=10))` → `CachedUnitOfWork`
        - Кэширует результат `uow.teams.get_by_id`
        - При промахе → БД → сохранение в кэш

    Возможные исключения:
        HTTPException: 404, если команда не найдена.
    """
    async with data_manager.cache(timedelta(minutes=10)) as cuow:
        team = await cuow.teams.get_by_id(team_id)
        if team is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Команда не найдена",
            )

        return TeamSchema.model_validate(team)


# —————— 2. POST /teams — создание команды ——————

class TeamCreate(BaseModel):
    """Входная схема создания команды."""
    name: str
    manager_id: UUID


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
async def create_team(
    team_data: Annotated[TeamCreate, Body(...)],
    data_manager: DependsDataManager,
):
    """
    Создание команды через TeamService.

    Поведение:
        - Открывает обычный UnitOfWork (для write-операций).
        - Создаёт `TeamService` с `uow.teams` и `uow.users`.
        - Вызывает `team_service.create_team(...)`.
        - Возвращает созданную команду.

    Исключения:
        TeamAlreadyExists: Если команда с таким названием уже существует.
        HTTPException: 404, если менеджер не найден.
    """
    async with data_manager() as uow:
        team_service = TeamService()
        try:
            team = await team_service.create_team(
                team_repo=uow.teams,
                user_repo=uow.users,
                name=team_data.name,
                manager_id=team_data.manager_id,
            )
            return team
        except TeamAlreadyExists as ex:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ex.detail,
            )
        except Exception as ex:
            if "Менеджер не найден" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Менеджер не найден",
                )
            raise  # Передаём неизвестные ошибки дальше


# —————— 3. GET /teams — список команд (с пагинацией и кэшированием) ——————


@team_router.get(
    "",
    response_model=List[TeamSchema],
    status_code=status.HTTP_200_OK,
    summary="Получить все команды",
    description="Возвращает список всех команд с пагинацией. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список команд (может быть пустым)"},
    },
)
async def get_all_teams(
    data_manager: DependsDataManager,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Количество записей на страницу")] = 10,
):
    """
    Получение всех команд с пагинацией через кэшированный Unit of Work.

    Использование кэша:
        - `data_manager.cache(timedelta(minutes=5))`
        - Кэширует результат `uow.teams.get_all_paginated`

    Возвращает:
        list[TeamSchema]: Список команд на странице.
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        teams, total = await cuow.teams.get_all_paginated(page=page, page_size=page_size)
        return [TeamSchema.model_validate(team) for team in teams]


# —————— 4. PATCH /teams/{team_id} — частичное обновление ——————

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
async def update_team(
    team_id: UUID,
    team_update: Annotated[TeamUpdateSheme, Body(...)],
    data_manager: DependsDataManager,
):
    """
    Обновление команды через репозиторий.

    Поведение:
        - Использует `uow.teams.update(...)`.
        - Не кэширует — write-операция.
        - Выбрасывает 404 при отсутствии команды.

    Исключения:
        HTTPException: 404, если команда не найдена.
    """
    async with data_manager() as uow:
        existing = await uow.teams.get_by_id(team_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Команда не найдена",
            )

        # Обновляем только непустые поля (в `TeamUpdateSheme` — `name: Optional[str]`)
        if team_update.name is not None:
            existing.name = team_update.name

        updated_team = await uow.teams.update(existing)
        return TeamSchema.model_validate(updated_team)


# —————— 5. DELETE /teams/{team_id} — удаление команды ——————

@team_router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить команду",
    description="Удаляет команду по ID. Данные не кэшируются (изменяют состояние).",
    responses={
        204: {"description": "Команда удалена"},
        404: {"description": "Команда не найдена"},
    },
)
async def delete_team(
    team_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Удаление команды через репозиторий.

    Поведение:
        - Использует `uow.teams.delete(...)`.
        - Не кэширует — write-операция.
        - Выбрасывает 404 при отсутствии команды.
    """
    async with data_manager() as uow:
        existing = await uow.teams.get_by_id(team_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Команда не найдена",
            )

        await uow.teams.delete(existing)
        return None  # FastAPI автоматически вернёт 204