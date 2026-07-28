"""
Обработчики (Handlers) для управления командами (Teams).

Этот модуль содержит бизнес-логику и взаимодействие с сервисами/БД.
Вызывается из API-слоя.

Функции:
    get_team_by_id_handler — получение команды по ID.
    create_team_handler — создание команды.
    get_all_teams_handler — получение списка команд.
    update_team_handler — обновление команды.
    delete_team_handler — удаление команды.
"""

from datetime import timedelta
from typing import List
from uuid import UUID

from fastapi import HTTPException, status

from app.src.api.api_utils import DataManager
from app.src.api.exceptions import TeamAlreadyExists
from app.src.api.services.team_service import TeamService
from app.src.api.shems import TeamCreate, TeamSchema, TeamUpdateSheme


async def get_team_by_id_handler(
    team_id: UUID,
    data_manager: DataManager,
) -> TeamSchema:
    """
    Получение команды по ID через кэшированный Unit of Work.

    Аргументы:
        team_id (UUID): ID команды.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TeamSchema: Данные команды.

    Дополнительная информация:
        - Кэширование TTL: 10 минут.
        - Используется `uow.teams.get_by_id`.

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


async def create_team_handler(
    team_data: TeamCreate,
    data_manager: DataManager,
) -> TeamSchema:
    """
    Создание команды через TeamService.

    Аргументы:
        team_data (TeamCreate): Данные команды.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TeamSchema: Созданная команда.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация уникальности названия: если команда существует — 409.

    Возможные исключения:
        HTTPException: 409, если команда с таким названием уже существует.
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
            return TeamSchema.model_validate(team)
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
            raise


async def get_all_teams_handler(
    page: int,
    page_size: int,
    data_manager: DataManager,
) -> List[TeamSchema]:
    """
    Получение всех команд с пагинацией через кэшированный Unit of Work.

    Аргументы:
        page (int): Номер страницы.
        page_size (int): Размер страницы.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        List[TeamSchema]: Список команд на странице.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется `uow.teams.get_all_paginated`.

    Возможные исключения:
        Нет явных исключений, кроме типовых ошибок БД.
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        teams, _ = await cuow.teams.get_all_paginated(page=page, page_size=page_size)
        return [TeamSchema.model_validate(team) for team in teams]


async def update_team_handler(
    team_id: UUID,
    team_update: TeamUpdateSheme,
    data_manager: DataManager,
) -> TeamSchema:
    """
    Обновление команды через TeamService.

    Аргументы:
        team_id (UUID): ID команды.
        team_update (TeamUpdateSheme): Обновляемые данные.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TeamSchema: Обновлённая команда.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Обновляются только непустые поля.

    Возможные исключения:
        HTTPException: 404, если команда не найдена.
    """
    async with data_manager() as uow:
        existing = await uow.teams.get_by_id(team_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Команда не найдена",
            )

        if team_update.name is not None:
            existing.name = team_update.name

        updated_team = await uow.teams.update(existing)
        return TeamSchema.model_validate(updated_team)


async def delete_team_handler(
    team_id: UUID,
    data_manager: DataManager,
) -> None:
    """
    Удаление команды через TeamService.

    Аргументы:
        team_id (UUID): ID команды.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        None: Операция удаления не возвращает данные.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если команда не найдена.
    """
    async with data_manager() as uow:
        existing = await uow.teams.get_by_id(team_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Команда не найдена",
            )

        await uow.teams.delete(existing)