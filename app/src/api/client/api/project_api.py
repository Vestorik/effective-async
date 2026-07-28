# app/src/api/routes/projects.py
"""
Эндпоинты управления проектами (Projects).

Роуты:
    GET /projects/{project_id} — получение проекта по ID (кэш 10 мин)
    POST /projects — создание проекта (с привязкой к командам)
    GET /teams/{team_id}/projects — получение проектов команды (кэш 5 мин)
    PATCH /projects/{project_id} — частичное обновление проекта
    DELETE /projects/{project_id} — удаление проекта
    GET /users/{user_id}/projects — получение проектов пользователя (кэш 5 мин)

Правила:
    - Для чтения используем `CachedUnitOfWork` с TTL.
    - Для записи — обычный `UnitOfWork`.
    - Валидация прав (manager/admin) делается в handlers.
    - Все исключения привязаны к `app.src.api.exceptions`.
    - Используем `DependsDataManager` для инъекции `DataManager`.
    - Возвращаем только безопасные схемы (`ProjectSchema`).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, status

from app.src.api.api_utils import DependsDataManager
from app.src.api.handlers.project_handlers import (
    create_project,
    delete_project,
    get_project_by_id,
    get_projects_for_team,
    get_projects_for_user,
    update_project,
)
from app.src.api.shems import ProjectCreate, ProjectSchema, ProjectUpdate

project_router = APIRouter(prefix="/projects", tags=["Проекты"])


@project_router.get(
    "/{project_id}",
    response_model=ProjectSchema,
    status_code=status.HTTP_200_OK,
    summary="Получить проект по ID",
    description="Возвращает проект с указанным ID. Данные кэшируются в Redis на 10 минут.",
    responses={
        200: {"description": "Проект найден"},
        404: {"description": "Проект не найден"},
    },
)
async def get_project_by_id_api(
    project_id: UUID,
    data_manager: DependsDataManager,
):
    return await get_project_by_id(project_id, data_manager)


@project_router.post(
    "",
    response_model=ProjectSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый проект",
    description="Создаёт проект и привязывает его к командам. Учитывает уникальность названия.",
    responses={
        201: {"description": "Проект успешно создан"},
        400: {"description": "Проект с таким названием уже существует"},
        404: {"description": "Одна из команд не найдена"},
    },
)
async def create_project_api(
    project_data: Annotated[ProjectCreate, ...],
    data_manager: DependsDataManager,
):
    return await create_project(project_data, data_manager)


@project_router.get(
    "/teams/{team_id}/projects",
    response_model=list[ProjectSchema],
    status_code=status.HTTP_200_OK,
    summary="Получить все проекты команды",
    description="Возвращает список проектов, в которых участвует команда. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список проектов (может быть пустым)"},
        404: {"description": "Команда не найдена"},
    },
)
async def get_projects_for_team_api(
    team_id: UUID,
    data_manager: DependsDataManager,
):
    return await get_projects_for_team(team_id, data_manager)


@project_router.patch(
    "/{project_id}",
    response_model=ProjectSchema,
    status_code=status.HTTP_200_OK,
    summary="Частичное обновление проекта",
    description="Обновляет название, описание и/или команды проекта. Не кэшируется (изменяет состояние).",
    responses={
        200: {"description": "Проект успешно обновлён"},
        404: {"description": "Проект не найден"},
    },
)
async def update_project_api(
    project_id: UUID,
    project_update: Annotated[ProjectUpdate, ...],
    data_manager: DependsDataManager,
):
    return await update_project(project_id, project_update, data_manager)


@project_router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить проект",
    description="Удаляет проект по ID. Не кэшируется (изменяет состояние).",
    responses={
        204: {"description": "Проект удалён"},
        404: {"description": "Проект не найден"},
    },
)
async def delete_project_api(
    project_id: UUID,
    data_manager: DependsDataManager,
):
    return await delete_project(project_id, data_manager)


@project_router.get(
    "/users/{user_id}/projects",
    response_model=list[ProjectSchema],
    status_code=status.HTTP_200_OK,
    summary="Получить все проекты пользователя",
    description="Возвращает список проектов, в которых участвует пользователь (через команды и задачи). Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список проектов (может быть пустым)"},
        404: {"description": "Пользователь не найден"},
    },
)
async def get_projects_for_user_api(
    user_id: UUID,
    data_manager: DependsDataManager,
):
    return await get_projects_for_user(user_id, data_manager)
