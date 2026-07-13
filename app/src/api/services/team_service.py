"""
Сервис управления командами.

Методы:
    create_team: Создаёт команду и назначает создателя менеджером.
    get_team_by_id: Получает команду по ID.
    get_teams_for_user: Получает все команды пользователя.
    join_team: Присоединение к команде (заглушка).

Ограничения:
    - invite_code пока не реализован.
    - Проверка прав (доступ только менеджерам) должна быть реализована в handlers.py.
"""

from datetime import datetime, timezone
from logging import getLogger
from typing import List
from uuid import UUID

from app.src.api.exceptions import TeamAlreadyExists, TeamNotFound
from app.src.api.shems import TeamSchema
from app.src.dal.database.models import TeamModel
from app.src.dal.database.repositories import UserRepository, TeamRepository

logger = getLogger(__name__)


class TeamService:
    """
    Сервис управления командами.

    Взаимодействует с репозиториями через конкретные экземпляры (`TeamRepository`, `UserRepository`).
    Это позволяет использовать сервис как с `UnitOfWork`, так и с `session_transaction`.

    Аргументы:
        None (все зависимости внедряются через методы).

    Методы:
        create_team
        get_team_by_id
        get_teams_for_user
    """

    async def create_team(
        self,
        team_repo: TeamRepository,
        user_repo: UserRepository,
        name: str,
        manager_id: UUID
    ) -> TeamSchema:
        """
        Создаёт команду и назначает создателя менеджером.

        Аргументы:
            team_repo: Экземпляр TeamRepository.
            user_repo: Экземпляр UserRepository.
            name (str): Название команды.
            manager_id (UUID): ID менеджера.

        Возвращает:
            TeamSchema: Созданная команда.

        Исключения:
            TeamAlreadyExists: Если команда с таким названием уже существует.
        """
        existing = await team_repo.get_by_name(name)
        if existing:
            raise TeamAlreadyExists()

        team = TeamModel(
            name=name,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        await team_repo.create(team)

        # Назначаем менеджера
        user = await user_repo.get_by_id(manager_id)
        if user is None:
            raise Exception("Менеджер не найден.")

        user.team_id = team.id
        await user_repo.update(user)

        return TeamSchema.model_validate(team)

    async def get_team_by_id(
        self,
        team_repo: TeamRepository,
        team_id: UUID
    ) -> TeamSchema:
        """
        Получает команду по ID.

        Аргументы:
            team_repo: Экземпляр TeamRepository.
            team_id (UUID): ID команды.

        Возвращает:
            TeamSchema: Команда.

        Исключения:
            TeamNotFound: Если команда не найдена.
        """
        team = await team_repo.get_by_id(team_id)
        if not team:
            raise TeamNotFound()
        return TeamSchema.model_validate(team)

    async def get_teams_for_user(
        self,
        user_repo: UserRepository,
        user_id: UUID
    ) -> List[TeamSchema]:
        """
        Получает все команды, к которым принадлежит пользователь.

        Аргументы:
            user_repo: Экземпляр UserRepository.
            user_id (UUID): ID пользователя.

        Возвращает:
            list[TeamSchema]: Список команд (обычно — одна).
        """
        user = await user_repo.get_by_id(user_id)
        if not user or not user.team_id:
            return []
        # Для получения команды используем TeamRepository (не реализовано, добавим позже)
        raise NotImplementedError("get_teams_for_user требует реализации через TeamRepository")