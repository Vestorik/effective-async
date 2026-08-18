# app/src/api/handlers/project_handlers.py
"""
Обработчики (Handlers) для управления проектами (Projects).

Этот модуль содержит бизнес-логику и взаимодействие с сервисами/БД.
Вызывается из API-слоя.

Функции:
    get_project_by_id — получение проекта по ID (с кэшем или без, логика внутри).
    create_project — создание проекта.
    get_projects_for_team — получение проектов команды.
    update_project — обновление проекта.
    delete_project — удаление проекта.
    get_projects_for_user — получение проектов пользователя.
"""

from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException, status

from app.src.api.utils.api_utils import DataManager
from app.src.api.exceptions import ProjectNotFound
from app.src.api.services.project_service import ProjectService
from app.src.api.shems import ProjectCreate, ProjectSchema, ProjectUpdate


async def get_project_by_id(
    project_id: UUID,
    data_manager: DataManager,
) -> ProjectSchema:
    """
    Получение проекта по ID через кэшированный Unit of Work.

    Аргументы:
        project_id (UUID): ID проекта.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def create_project(
    project_data: ProjectCreate,
    data_manager: DataManager,
) -> ProjectSchema:
    """
    Создание проекта через ProjectService.

    Аргументы:
        project_data (ProjectCreate): Данные проекта.
        data_manager (DataManager): Внедрённый менеджер данных.

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
            detail = str(ex)
            if "уже существует" in detail:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=detail,
                )
            elif "не найдена" in detail:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Одна из команд не найдена",
                )
            raise


async def get_projects_for_team(
    team_id: UUID,
    data_manager: DataManager,
) -> list[ProjectSchema]:
    """
    Получение проектов команды через кэшированный Unit of Work.

    Аргументы:
        team_id (UUID): ID команды.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    data_manager: DataManager,
) -> ProjectSchema:
    """
    Обновление проекта через ProjectService.

    Аргументы:
        project_id (UUID): ID проекта.
        project_update (ProjectUpdate): Обновляемые данные.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def delete_project(
    project_id: UUID,
    data_manager: DataManager,
) -> None:
    """
    Удаление проекта через ProjectService.

    Аргументы:
        project_id (UUID): ID проекта.
        data_manager (DataManager): Внедрённый менеджер данных.

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
        except ProjectNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


async def get_projects_for_user(
    user_id: UUID,
    data_manager: DataManager,
) -> list[ProjectSchema]:
    """
    Получение всех проектов пользователя через кэшированный Unit of Work.

    Аргументы:
        user_id (UUID): ID пользователя.
        data_manager (DataManager): Внедрённый менеджер данных.

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