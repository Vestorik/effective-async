from collections.abc import Sequence
from logging import getLogger
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.src.api.services.base_services import BaseService
from app.src.api.shems import (
    ProjectWithTasksOutSheme,
    TaskWithExecutorsOutSheme,
    TeamWithProjectsOutSheme,
)
from app.src.dal.database.repositories import (
    ProjectRepository,
    TaskExecutorRepository,
    TaskRepository,
    TeamRepository,
)

logger = getLogger(__name__)


class DashboardService(BaseService):
    """
    Сервис для формирования данных дашборда.

    Агрегирует данные из различных репозиториев для отображения на главной странице:
    список команд с их проектами, а внутри проектов — задачи с исполнителями.

    Методы:
        get_dashboard_data: Формирует полную структуру данных для дашборда.
        _fetch_teams_with_projects: Вспомогательный метод для получения команд и проектов.
        _fetch_tasks_with_executors: Вспомогательный метод для получения задач и исполнителей.
    """

    def __init__(self, session: AsyncSession):
        """
        Инициализирует сервис сессией.

        Аргументы:
            session (AsyncSession): Асинхронная сессия SQLAlchemy.
        """
        self.session = session

    async def get_dashboard_data(self, user_id: UUID) -> list[TeamWithProjectsOutSheme]:
        """
        Получает данные для дашборда.

        Возвращает список команд, в которых состоит пользователь (или все команды,
        если логика позволяет). Для каждой команды возвращает связанные проекты.
        Для каждого проекта возвращает задачи с исполнителями.

        Аргументы:
            user_id (UUID): ID текущего пользователя для фильтрации.

        Возвращает:
            List[TeamWithProjectsOutSheme]: Структурированный список команд и проектов.
        """
        team_repo = TeamRepository(self.session)
        project_repo = ProjectRepository(self.session)
        task_repo = TaskRepository(self.session)
        executor_repo = TaskExecutorRepository(self.session)

        all_teams = await team_repo.get_all()

        result_teams = []

        for team in all_teams:
            # Получаем проекты для команды
            projects = await self._get_projects_for_team(project_repo, team.id)

            project_objects = []
            for proj in projects:
                # Получаем задачи для проекта
                tasks = await self._get_tasks_for_project(task_repo, proj.id)

                # Получаем исполнителей для каждой задачи
                enriched_tasks = await self._enrich_tasks_with_executors(
                    executor_repo, task_repo, tasks
                )

                task_shemes = [
                    TaskWithExecutorsOutSheme.model_validate(t) for t in enriched_tasks
                ]

                proj_schema = ProjectWithTasksOutSheme(
                    name=proj.name, description=proj.description, tasks=task_shemes
                )
                project_objects.append(proj_schema)

            team_schema = TeamWithProjectsOutSheme(
                name=team.name,
                member_count=len(await self._get_members_for_team(team_repo, team.id)),
                projects=project_objects,
            )
            result_teams.append(team_schema)

        return result_teams

    async def _get_projects_for_team(
        self, project_repo: ProjectRepository, team_id: UUID
    ) -> Sequence:
        """
        Получает список проектов для конкретной команды.

        Аргументы:
            project_repo: ProjectRepository
            team_id (UUID): ID команды

        Возвращает:
            list: Список ProjectModel
        """
        return await project_repo.get_teams_for_project(team_id)

    async def _get_tasks_for_project(
        self, task_repo: TaskRepository, project_id: UUID
    ) -> Sequence:
        """
        Получает список задач для проекта.

        Аргументы:
            task_repo: TaskRepository
            project_id (UUID): ID проекта

        Возвращает:
            list: Список TaskModel
        """
        return await task_repo.get_by_project_id(project_id)

    async def _get_members_for_team(
        self, team_repo: TeamRepository, team_id: UUID
    ) -> list:
        """
        Получает список участников команды.

        Аргументы:
            team_repo: TeamRepository
            team_id (UUID): ID команды

        Возвращает:
            list: Список UserModel
        """
        # Предполагается, что в TeamModel есть связь users
        team = await team_repo.get_by_id(team_id)
        if team and hasattr(team, "users"):
            return team.users
        return []

    async def _enrich_tasks_with_executors(
        self,
        executor_repo: TaskExecutorRepository,
        task_repo: TaskRepository,
        tasks: Sequence,
    ) -> list:
        """
        Обогащает задачи данными об исполнителях.

        Аргументы:
            executor_repo: TaskExecutorRepository
            task_repo: TaskRepository
            tasks (list): Список TaskModel

        Возвращает:
            list: Список TaskModel с загруженными исполнителями
        """
        enriched_tasks = []
        for task in tasks:
            executors = await executor_repo.get_executors_for_task(task.id)
            task.executors = executors
            enriched_tasks.append(task)
        return enriched_tasks
