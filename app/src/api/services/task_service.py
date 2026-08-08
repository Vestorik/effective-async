"""
Сервис управления задачами.

Реализует CRUD-операции для задач:
- create_task: создаёт новую задачу.
- list_tasks: получает задачи команды с фильтрацией.
- update_task: обновляет задачу.
- delete_task: удаляет задачу.

Приоритеты:
- Валидация прав (manager/admin) делается в handlers.
- Валидация parent_id (подзадача) — через check_parent_task.
"""

from logging import getLogger
from typing import Optional, Sequence
from uuid import UUID
from app.src.api.services.base_services import BaseService
from app.src.api.exceptions import TaskNotFound, TeamNotFound
from app.src.dal.database.repositories import TeamRepository, TaskRepository, TaskExecutorRepository
from app.src.dal.database.models import TaskModel, TaskExecutorModel

logger = getLogger(__name__)


class TaskService(BaseService):
    """
    Сервис управления задачами.

    Взаимодействует с репозиториями через конкретные экземпляры:
    - TaskRepository
    - TaskExecutorRepository
    - UserRepository, TeamRepository (для валидации доступа)

    Методы:
        create_task: создаёт новую задачу.
        list_tasks: получает задачи команды с фильтрацией по приоритету.
        update_task: обновляет задачу.
        delete_task: удаляет задачу.
    """

    async def create_task(
        self,
        task_repo: TaskRepository,
        task_executor_repo: TaskExecutorRepository,
        team_repo: TeamRepository,
        user_id: UUID,
        team_id: UUID,
        name: str,
        description: Optional[str] = None,
        priority: str = "medium",  # low, medium, high
        parent_id: Optional[UUID] = None,
        executor_ids: Optional[list[UUID]] = None,
    ) -> TaskModel:
        """
        Создаёт новую задачу.

        Аргументы:
            task_repo: TaskRepository
            task_executor_repo: TaskExecutorRepository
            team_repo: TeamRepository
            user_id: UUID — ID пользователя, создающего задачу
            team_id: UUID — ID команды
            name: str
            description: Optional[str]
            priority: str — low/medium/high
            parent_id: Optional[UUID] — если задача подзадача
            executor_ids: Optional[list[UUID]] — кто исполнитель

        Возвращает:
            TaskModel — созданная задача

        Исключения:
            TeamNotFound: если команда не найдена
            UserNotFound: если исполнитель не состоит в команде (проверка в handlers)
        """
        # Проверка доступа к команде
        team = await team_repo.get_by_id(team_id)
        if not team:
            raise TeamNotFound()

        # Валидация parent_id
        if parent_id:
            parent_task = await task_repo.get_by_id(parent_id)
            if not parent_task or parent_task.project_id:
                raise Exception("Родительская задача не найдена или неверная структура")

        task = TaskModel(
            name=name,
            description=description,
            priority=priority,
            team_id=team_id,
            parent_id=parent_id,
        )
        await task_repo.create(task)

        # Добавляем исполнителей
        if executor_ids:
            for executor_id in executor_ids:
                task_executor = TaskExecutorModel(
                    task_id=task.id,
                    user_id=executor_id,
                )
                await task_executor_repo.create(task_executor)

        return task

    async def list_tasks(
        self,
        task_repo: TaskRepository,
        team_id: UUID,
        priority: Optional[str] = None,
    ) -> Sequence:
        """
        Получает задачи команды с фильтрацией.

        Аргументы:
            task_repo: TaskRepository
            team_id: UUID
            priority: Optional[str] — low/medium/high

        Возвращает:
            list[TaskModel]
        """
        return await task_repo.get_tasks_by_team_and_priority(team_id, priority)

    async def update_task(
        self,
        task_repo: TaskRepository,
        task_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TaskModel:
        """
        Обновляет задачу.

        Аргументы:
            task_repo: TaskRepository
            task_id: UUID
            name: Optional[str]
            description: Optional[str]
            priority: Optional[str]

        Возвращает:
            TaskModel — обновлённая задача

        Исключения:
            TaskNotFound
        """
        task = await task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFound()

        if name is not None:
            task.name = name
        if description is not None:
            task.description = description


        await task_repo.update(task)
        return task

    async def delete_task(
        self,
        task_repo: TaskRepository,
        task_id: UUID,
    ) -> None:
        """
        Удаляет задачу.

        Аргументы:
            task_repo: TaskRepository
            task_id: UUID

        Исключения:
            TaskNotFound
        """
        task = await task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFound()
        await task_repo.delete(task)
        
    async def add_executor(
        self,
        task_repo: TaskRepository,
        task_executor_repo: TaskExecutorRepository,
        task_id: UUID,
        user_id: UUID,
        estimate: int | None = None,
    ) -> TaskExecutorModel:
        """
        Добавляет исполнителя к задаче.

        Аргументы:
            task_repo (TaskRepository): Репозиторий задач.
            task_executor_repo (TaskExecutorRepository): Репозиторий исполнителей.
            task_id (UUID): ID задачи.
            user_id (UUID): ID пользователя.
            estimate (int | None): Оценка (если есть).

        Возвращает:
            TaskExecutorModel: Созданная связка "задача-исполнитель".

        Исключения:
            TaskNotFound: Если задача не найдена.
            Exception: Если исполнитель уже добавлен.
        """
        task = await task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFound()

        existing = await task_executor_repo.get_by_task_and_user(task_id, user_id)
        if existing:
            raise Exception("Исполнитель уже добавлен к задаче")

        executor = TaskExecutorModel(
            task_id=task_id,
            user_id=user_id,
            estimate=estimate,
        )
        await task_executor_repo.create(executor)
        return executor

    async def update_executor_estimate(
        self,
        task_executor_repo: TaskExecutorRepository,
        task_id: UUID,
        user_id: UUID,
        estimate: int,
    ) -> TaskExecutorModel:
        """
        Обновляет оценку исполнителя.

        Аргументы:
            task_executor_repo (TaskExecutorRepository): Репозиторий исполнителей.
            task_id (UUID): ID задачи.
            user_id (UUID): ID пользователя.
            estimate (int): Новая оценка (1–5).

        Возвращает:
            TaskExecutorModel: Обновлённая связка.

        Исключения:
            Exception: Если связка не найдена.
        """
        executor = await task_executor_repo.get_by_task_and_user(task_id, user_id)
        if not executor:
            raise Exception("Связка задача-исполнитель не найдена")
        executor.estimate = estimate
        await task_executor_repo.update(executor)
        return executor