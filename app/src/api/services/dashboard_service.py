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
    ProjectModel,
    ProjectRepository,
    TaskExecutorRepository,
    TaskModel,
    TaskRepository,
    TeamModel,
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

    async def get_dashboard_data(self, user_id: UUID) -> dict:
        """
        Получает данные для дашборда.

        Аргументы:
            user_id (UUID): ID текущего пользователя (используется для фильтрации, если требуется).

        Возвращает:
            dict: Словарь с данными для дашборда, содержащий:
                - 'teams': список команд с их проектами.
                - 'projects': список всех проектов (включая те, что не привязаны к текущим командам, если возможно, или все проекты).
        
        Замечание: 
        В текущей архитектуре проекты привязаны к командам. Если проект не отображается, 
        значит он не привязан ни к одной из загруженных команд. 
        Здесь мы возвращаем два отдельных списка для гибкости шаблона.
        """
        team_repo = TeamRepository(self.session)
        
        # 1. Получаем все команды
        all_teams = await team_repo.get_all()
        
        result_teams = []
        for team in all_teams:
            team_with_data = await team_repo.get_team_with_projects(team.id)  # ty: ignore[invalid-argument-type]
            if team_with_data:
                team_schema = self._serialize_team(team_with_data)
                result_teams.append(team_schema)
        
        # 2. Получаем все проекты (без привязки к команде в цикле)
        # Это позволит отобразить проекты, которые могут быть "сиротами" или привязаны к командам из другой выборки
        # Или просто все проекты в системе, если доступ разрешен.
        # Используем selectinload для предварительной загрузки задач и исполнителей для всех проектов сразу
        all_projects = await self._fetch_all_projects_with_tasks()
        
        # Если нужно фильтровать проекты по пользователю, это можно сделать здесь
        # for MVP: возвращаем все проекты
        filtered_projects = all_projects 
        
        return {
            "teams": result_teams,
            "projects": filtered_projects
        }
        
    async def _fetch_all_projects_with_tasks(self) -> list[ProjectWithTasksOutSheme]:
        """
        Загружает все проекты с задачами и исполнителями для глобального списка.

        Возвращает:
            list[ProjectWithTasksOutSheme]: Список проектов.
        """
        # Используем репозиторий или прямой запрос для получения всех проектов
        # Для оптимизации используем selectinload
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        stmt = (
            select(ProjectModel)
            .options(
                selectinload(ProjectModel.project_tasks)
                    .selectinload(TaskModel.executors)
            )
        )
        result = await self.session.execute(stmt)
        projects = result.scalars().unique().all()
        
        schemas = []
        for proj in projects:
            tasks = []
            for task in proj.project_tasks:
                executors = task.executors if task.executors else []
                task_schema = TaskWithExecutorsOutSheme(
                    name=task.name,
                    description=task.description,
                    executors=executors,
                )
                tasks.append(task_schema)
            
            proj_schema = ProjectWithTasksOutSheme(
                name=proj.name,
                description=proj.description,
                tasks=tasks,
            )
            schemas.append(proj_schema)
            
        return schemas
    
    def _serialize_team(self, team: TeamModel) -> TeamWithProjectsOutSheme:
        """
        Преобразует ORM-модель команды в Pydantic-схему для отправки в ответе.

        Аргументы:
            team (TeamModel): Объект команды с предзагруженными связями.

        Возвращает:
            TeamWithProjectsOutSheme: Схема данных команды.
        """
        projects = []
        for proj in team.team_projects:
            tasks = []
            for task in proj.project_tasks:
                # Исполнители уже загружены через selectinload
                executors = task.executors if task.executors else []
                task_schema = TaskWithExecutorsOutSheme(
                    name=task.name,
                    description=task.description,
                    executors=executors,
                )
                tasks.append(task_schema)
            
            proj_schema = ProjectWithTasksOutSheme(
                name=proj.name,
                description=proj.description,
                tasks=tasks,
            )
            projects.append(proj_schema)

        return TeamWithProjectsOutSheme(
            name=team.name,
            member_count=len(team.users),
            projects=projects,
        )

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
