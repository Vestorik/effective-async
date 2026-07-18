
"""
Сервис управления исполнителями задач.

Методы:
    add_executor: добавляет исполнителя к задаче.
    remove_executor: удаляет исполнителя из задачи.
    update_estimate: обновляет оценку исполнителя.
    get_executors_for_task: получает всех исполнителей задачи.
    get_tasks_for_user: получает все задачи пользователя.

Ограничения:
    - Валидация прав (manager/admin) делается в handlers.
    - Исполнитель должен состоять в команде задачи.
"""

from logging import getLogger
from typing import List, Tuple, Sequence
from uuid import UUID

from app.src.api.exceptions import TaskNotFound, UserNotFound
from app.src.api.shems import TaskExecutorOutSheme
from app.src.dal.database.models import TaskExecutorModel, UserModel, TaskModel
from app.src.dal.database.repositories import (
    TaskRepository,
    TaskExecutorRepository,
)
from app.src.api.services.base_services import BaseService
logger = getLogger(__name__)


class TaskExecutorService(BaseService):
    """
    Сервис управления исполнителями задач.

    Взаимодействует с репозиториями через конкретные экземпляры:
        - TaskExecutorRepository
        - TaskRepository
        - UserRepository

    Методы:
        add_executor
        remove_executor
        update_estimate
        get_executors_for_task
        get_tasks_for_user
    """

    async def add_executor(
        self,
        task_repo: TaskRepository,
        task_executor_repo: TaskExecutorRepository,
        task_id: UUID,
        user_id: UUID,
        estimate: int | None = None,
    ) -> TaskExecutorOutSheme:
        """
        Добавляет исполнителя к задаче.

        Аргументы:
            task_repo: TaskRepository
            task_executor_repo: TaskExecutorRepository
            task_id: UUID
            user_id: UUID
            estimate: int | None — оценка (опционально)

        Возвращает:
            TaskExecutorOutSheme — созданная связка

        Исключения:
            TaskNotFound: если задача не найдена
            UserNotFound: если пользователь не найден
        """
        task = await task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFound()

        user = await task_executor_repo.session.get(UserModel, user_id)
        if not user:
            raise UserNotFound()

        existing = await task_executor_repo.get_by_task_and_user(task_id, user_id)
        if existing:
            raise Exception("Исполнитель уже добавлен к задаче")

        executor = TaskExecutorModel(
            task_id=task_id,
            user_id=user_id,
            estimate=estimate,
        )
        await task_executor_repo.create(executor)

        return TaskExecutorOutSheme.model_validate(executor)

    async def remove_executor(
        self,
        task_executor_repo: TaskExecutorRepository,
        task_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Удаляет исполнителя из задачи.

        Аргументы:
            task_executor_repo: TaskExecutorRepository
            task_id: UUID
            user_id: UUID

        Исключения:
            TaskNotFound: если связка не найдена
        """
        executor = await task_executor_repo.get_by_task_and_user(task_id, user_id)
        if not executor:
            raise Exception("Связка задача-исполнитель не найдена")
        await task_executor_repo.delete(executor)

    async def update_estimate(
        self,
        task_executor_repo: TaskExecutorRepository,
        task_id: UUID,
        user_id: UUID,
        estimate: int,
    ) -> TaskExecutorOutSheme:
        """
        Обновляет оценку исполнителя.

        Аргументы:
            task_executor_repo: TaskExecutorRepository
            task_id: UUID
            user_id: UUID
            estimate: int — новая оценка

        Возвращает:
            TaskExecutorOutSheme — обновлённая связка

        Исключения:
            Exception: если связка не найдена
        """
        executor = await task_executor_repo.get_by_task_and_user(task_id, user_id)
        if not executor:
            raise Exception("Связка задача-исполнитель не найдена")
        executor.estimate = estimate
        await task_executor_repo.update(executor)
        return TaskExecutorOutSheme.model_validate(executor)

    async def get_executors_for_task(
        self,
        task_executor_repo: TaskExecutorRepository,
        task_id: UUID,
    ) -> List[TaskExecutorOutSheme]:
        """
        Получает всех исполнителей задачи.

        Аргументы:
            task_executor_repo: TaskExecutorRepository
            task_id: UUID

        Возвращает: 
            list[TaskExecutorOutSheme] — список исполнителей
        """
        executors = await task_executor_repo.get_executors_for_task(task_id)
        return [TaskExecutorOutSheme.model_validate(e) for e in executors]

    async def get_tasks_for_user(
        self,
        task_executor_repo: TaskExecutorRepository,
        user_id: UUID,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[Sequence[TaskModel], int]:
        """
        Получает все задачи пользователя с пагинацией.

        Аргументы:
            task_executor_repo: TaskExecutorRepository
            user_id: UUID
            page: int
            page_size: int

        Возвращает:
            (list[TaskModel], int) — список задач и их количество
        """
        tasks, total = await task_executor_repo.get_tasks_for_user(user_id)
        return tasks, total