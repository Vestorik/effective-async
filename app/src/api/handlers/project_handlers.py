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

from datetime import timedelta
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.src.api.api_utils import DependsDataManager
from app.src.api.exceptions import ProjectNotFound
from app.src.api.services.project_service import ProjectService
from app.src.api.shems import ProjectCreate, ProjectSchema, ProjectUpdate

project_router = APIRouter(prefix="/projects", tags=["Проекты"])


# —————— 1. GET /projects/{project_id} — кэшированный GET ——————


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
async def get_project_by_id(
    project_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Получение проекта по ID через кэшированный Unit of Work.

    Аргументы:
        project_id (UUID): ID проекта.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        ProjectSchema: Проект (без вложенных связей — для избежания рекурсии).

    Дополнительная информация:
        - Кэширование TTL: 10 минут.
        - Используется `uow.projects.get_by_id`.

    Возможные исключения:
        HTTPException: 404, если проект не найден.
    """
    async with data_manager.cache(timedelta(minutes=10)) as cuow:
        project = await cuow.projects.get_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Проект не найден",
            )

        return ProjectSchema.model_validate(project)


# —————— 2. POST /projects — создание проекта ——————


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
async def create_project(
    project_data: Annotated[ProjectCreate, ...],
    data_manager: DependsDataManager,
):
    """
    Создание проекта через ProjectService.

    Аргументы:
        project_data (ProjectCreate): Данные проекта.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        ProjectSchema: Созданный проект.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация уникальности названия: если проект существует — 400.

    Возможные исключения:
        HTTPException: 400, если проект с таким названием уже существует.
        HTTPException: 404, если одна из команд не найдена.
    """
    async with data_manager() as uow:
        project_service = ProjectService()

        try:
            project = await project_service.create_project(
                project_repo=uow.projects,
                team_repo=uow.teams,
                name=project_data.name,
                description=project_data.description,
                team_ids=project_data.team_ids,
            )
            return ProjectSchema.model_validate(project)
        except Exception as ex:
            if "уже существует" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(ex),
                )
            elif "не найдена" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Одна из команд не найдена",
                )
            raise


# —————— 3. GET /teams/{team_id}/projects — список проектов команды — кэшировано ——————


@project_router.get(
    "/teams/{team_id}/projects",
    response_model=List[ProjectSchema],
    status_code=status.HTTP_200_OK,
    summary="Получить все проекты команды",
    description="Возвращает список проектов, в которых участвует команда. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список проектов (может быть пустым)"},
        404: {"description": "Команда не найдена"},
    },
)
async def get_projects_for_team(
    team_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Получение проектов команды через кэшированный Unit of Work.

    Аргументы:
        team_id (UUID): ID команды.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        list[ProjectSchema]: Список проектов.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется `uow.projects.get_teams_for_project`.

    Возможные исключения:
        HTTPException: 404, если команда не найдена (через сервис).
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        project_service = ProjectService()
        try:
            projects = await project_service.get_projects_for_team(
                project_repo=cuow.projects,
                team_id=team_id,
            )
            return projects
        except ProjectNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


# —————— 4. PATCH /projects/{project_id} — частичное обновление ——————


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
async def update_project(
    project_id: UUID,
    project_update: Annotated[ProjectUpdate, ...],
    data_manager: DependsDataManager,
):
    """
    Обновление проекта через ProjectService.

    Аргументы:
        project_id (UUID): ID проекта.
        project_update (ProjectUpdate): Обновляемые данные.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        ProjectSchema: Обновлённый проект.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если проект не найден.
        HTTPException: 400, если один из team_id не найден.
    """
    async with data_manager() as uow:
        project_service = ProjectService()
        try:
            project = await project_service.update_project(
                project_repo=uow.projects,
                project_id=project_id,
                name=project_update.name,
                description=project_update.description,
                team_ids=project_update.team_ids,
            )
            return ProjectSchema.model_validate(project)
        except ProjectNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )
        except Exception as ex:
            if "не найдена" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Одна из команд не найдена",
                )
            raise


# —————— 5. DELETE /projects/{project_id} — удаление проекта ——————


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
async def delete_project(
    project_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Удаление проекта через ProjectService.

    Аргументы:
        project_id (UUID): ID проекта.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если проект не найден.
    """
    async with data_manager() as uow:
        project_service = ProjectService()
        try:
            await project_service.delete_project(
                project_repo=uow.projects,
                project_id=project_id,
            )
            return None  # FastAPI автоматически вернёт 204
        except ProjectNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


# —————— 6. GET /users/{user_id}/projects — список проектов пользователя — кэшировано ——————


@project_router.get(
    "/users/{user_id}/projects",
    response_model=List[ProjectSchema],
    status_code=status.HTTP_200_OK,
    summary="Получить все проекты пользователя",
    description="Возвращает список проектов, в которых участвует пользователь (через команды и задачи). Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список проектов (может быть пустым)"},
        404: {"description": "Пользователь не найден"},
    },
)
async def get_projects_for_user(
    user_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Получение всех проектов пользователя через кэшированный Unit of Work.

    Аргументы:
        user_id (UUID): ID пользователя.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        list[ProjectSchema]: Список проектов.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется `uow.projects.get_by_user_id`.

    Возможные исключения:
        HTTPException: 404, если пользователь не найден (через сервис).
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        project_service = ProjectService()
        try:
            projects = await project_service.get_projects_for_user(
                project_repo=cuow.projects,
                user_id=user_id,
            )
            return projects
        except ProjectNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )
