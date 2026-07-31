
"""
Сервис управления проектами.

Методы:
    create_project: создаёт проект.
    get_project_by_id: получает проект по ID.
    get_projects_for_team: получает проекты команды.
    get_projects_for_user: получает проекты, где участвует пользователь.
    update_project: обновляет проект.
    delete_project: удаляет проект.

Ограничения:
    - Валидация прав (manager/admin) делается в handlers.
    - Участие в проекте через команды (n:m team_projects).
"""

from datetime import datetime, timezone
from logging import getLogger
from typing import List
from uuid import UUID

from app.src.api.exceptions import ProjectNotFound
from app.src.api.shems import ProjectSchema
from app.src.dal.database.models import ProjectModel, TeamModel
from app.src.dal.database.repositories import ProjectRepository, TeamRepository
from app.src.api.services.base_services import BaseService
logger = getLogger(__name__)


class ProjectService(BaseService):
    """
    Сервис управления проектами.

    Взаимодействует с репозиториями через конкретные экземпляры:
        - ProjectRepository
        - TeamRepository (для валидации привязки команд)

    Методы:
        create_project
        get_project_by_id
        get_projects_for_team
        get_projects_for_user
        update_project
        delete_project
    """

    async def create_project(
        self,
        project_repo: ProjectRepository,
        team_repo: TeamRepository,
        name: str,
        description: str | None,
        team_ids: list[UUID] | None = None,
    ) -> ProjectSchema:
        """
        Создаёт новый проект и привязывает его к командам.

        Аргументы:
            project_repo: ProjectRepository
            team_repo: TeamRepository
            name: str
            description: str | None
            team_ids: list[UUID] | None — команды, участвующие в проекте

        Возвращает:
            ProjectSchema — созданный проект

        Исключения:
            ProjectNotFound: не используется в этом методе
        """
        existing = await project_repo.get_by_name(name)
        if existing:
            raise Exception(f"Проект с названием '{name}' уже существует")

        project = ProjectModel(
            name=name,
            description=description,
        )
        await project_repo.create(project)

        # Привязка команд (если указаны)
        if team_ids:
            for team_id in team_ids:
                team = await team_repo.get_by_id(team_id)
                if not team:
                    raise Exception(f"Команда с ID {team_id} не найдена")
                project.project_teams.append(team)

        project.updated_at = datetime.now(timezone.utc)
        await project_repo.update(project)

        return ProjectSchema.model_validate(project)

    async def get_project_by_id(
        self,
        project_repo: ProjectRepository,
        project_id: UUID,
    ) -> ProjectSchema:
        """
        Получает проект по ID.

        Аргументы:
            project_repo: ProjectRepository
            project_id: UUID

        Возвращает:
            ProjectSchema — проект

        Исключения:
            ProjectNotFound: если проект не найден
        """
        project = await project_repo.get_by_id(project_id)
        if not project:
            raise ProjectNotFound()
        return ProjectSchema.model_validate(project)

    async def get_projects_for_team(
        self,
        project_repo: ProjectRepository,
        team_id: UUID,
    ) -> List[ProjectSchema]:
        """
        Получает проекты, в которых участвует команда.

        Аргументы:
            project_repo: ProjectRepository
            team_id: UUID

        Возвращает:
            list[ProjectSchema] — список проектов
        """
        projects = await project_repo.get_teams_for_project(team_id)
        return [ProjectSchema.model_validate(p) for p in projects]

    async def get_projects_for_user(
        self,
        project_repo: ProjectRepository,
        user_id: UUID,
    ) -> List[ProjectSchema]:
        """
        Получает проекты, в которых участвует пользователь (через команды и задачи).

        Аргументы:
            project_repo: ProjectRepository
            user_id: UUID

        Возвращает:
            list[ProjectSchema] — список проектов
        """
        projects = await project_repo.get_by_user_id(user_id)
        return [ProjectSchema.model_validate(p) for p in projects]

    async def update_project(
        self,
        project_repo: ProjectRepository,
        project_id: UUID,
        name: str | None = None,
        description: str | None = None,
        team_ids: list[UUID] | None = None,
    ) -> ProjectSchema:
        """
        Обновляет проект.

        Аргументы:
            project_repo: ProjectRepository
            project_id: UUID
            name: str | None
            description: str | None
            team_ids: list[UUID] | None — новые команды

        Возвращает:
            ProjectSchema — обновлённый проект

        Исключения:
            ProjectNotFound
        """
        project = await project_repo.get_by_id(project_id)
        if not project:
            raise ProjectNotFound()

        if name is not None:
            project.name = name
        if description is not None:
            project.description = description

        # Обновление команд
        if team_ids is not None:
            project.project_teams.clear()
            for team_id in team_ids:
                team = await project_repo.session.get(TeamModel, team_id)
                if not team:
                    raise Exception(f"Команда с ID {team_id} не найдена")
                project.project_teams.append(team)

        project.updated_at = datetime.now(timezone.utc)
        await project_repo.update(project)
        return ProjectSchema.model_validate(project)

    async def delete_project(
        self,
        project_repo: ProjectRepository,
        project_id: UUID,
    ) -> None:
        """
        Удаляет проект.

        Аргументы:
            project_repo: ProjectRepository
            project_id: UUID

        Исключения:
            ProjectNotFound
        """
        project = await project_repo.get_by_id(project_id)
        if not project:
            raise ProjectNotFound()
        await project_repo.delete(project)