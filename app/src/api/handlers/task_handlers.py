# app/src/api/routes/tasks.py
"""
Эндпоинты управления задачами (Tasks).

Роуты:
    GET /tasks/{task_id} — кэшированный GET-запрос (10 мин)
    GET /teams/{team_id}/tasks — список задач команды (с фильтрацией и кэшированием)
    POST /teams/{team_id}/tasks — создание задачи
    PATCH /tasks/{task_id} — частичное обновление задачи
    DELETE /tasks/{task_id} — удаление задачи

Правила:
    - Для чтения используем `CachedUnitOfWork` с TTL.
    - Для записи — обычный `UnitOfWork`.
    - Валидация прав (manager/admin) делается в handlers (здесь — `user_id` и `team_id` из токена).
    - Все исключения привязаны к `app.src.api.exceptions`.
    - Возвращаем только безопасные схемы (`TaskOutSheme`, `TaskWithExecutorsSheme`).
"""

from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import HTTPException, status

from app.src.api.utils.api_utils import DataManager
from app.src.api.exceptions import TaskNotFound, TeamNotFound
from app.src.api.services.task_service import TaskService
from app.src.api.shems import (
    AddExecutor,
    TaskCreate,
    TaskCreateOutSheme,
    TaskExecutorOutSheme,
    TaskOutSheme,
    TaskUpdateSheme,
)


async def get_task_by_id(
    task_id: UUID,
    data_manager: DataManager,
) -> TaskOutSheme:
    """
    Получение задачи по ID через кэшированный Unit of Work.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskOutSheme: Задача, исключая executors, parent/sub_tasks для избежания рекурсии.

    Дополнительная информация:
        - Кэширование TTL: 10 минут.
        - Используется `uow.tasks.get_by_id`.

    Возможные исключения:
        HTTPException: 404, если задача не найдена.
    """
    async with data_manager.cache(timedelta(minutes=10)) as cuow:
        task = await cuow.tasks.get_by_id(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задача не найдена",
            )
        return TaskOutSheme.model_validate(task)


async def get_team_tasks(
    team_id: UUID,
    data_manager: DataManager,
    priority: str | None = None,
) -> list[TaskOutSheme]:
    """
    Получение задач команды с фильтрацией по приоритету через кэшированный Unit of Work.

    Аргументы:
        team_id (UUID): ID команды.
        data_manager (DataManager): Внедрённый менеджер данных.
        priority (Optional[str]): Фильтр по приоритету (`low`, `medium`, `high`).

    Возвращает:
        list[TaskOutSheme]: Список задач на странице.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется `uow.tasks.get_tasks_by_team_and_priority`.

    Возможные исключения:
        HTTPException: 404, если команда не найдена.
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        tasks = await cuow.tasks.get_tasks_by_team_and_priority(team_id, priority)
        return [TaskOutSheme.model_validate(task) for task in tasks]


async def create_task(
    team_id: UUID,
    task_data: TaskCreate,
    user_id: UUID,
    data_manager: DataManager,
) -> TaskCreateOutSheme:
    """
    Создание задачи через TaskService.

    Аргументы:
        team_id (UUID): ID команды.
        task_data (TaskCreate): Данные задачи.
        user_id (UUID): ID пользователя, создающего задачу.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskCreateOutSheme: Созданная задача.

    Дополнительная информация:
        - Валидация прав: `user_id` и `team_id` проверяются в `handlers.py`.
        - Валидация `parent_id` внутри `TaskService.create_task`.

    Возможные исключения:
        HTTPException: 404, если команда/родительская задача не найдены.
        HTTPException: 400, если приоритет неверный или структура подзадач нарушена.
    """
    async with data_manager() as uow:
        task_service = TaskService()
        try:
            task = await task_service.create_task(
                task_repo=uow.tasks,
                task_executor_repo=uow.task_executors,
                team_repo=uow.teams,
                user_id=user_id,
                team_id=team_id,
                name=task_data.name,
                description=task_data.description,
                priority=task_data.priority,
                parent_id=task_data.parent_id,
                executor_ids=task_data.executor_ids,
            )
            return TaskCreateOutSheme.model_validate(task)
        except TeamNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )
        except Exception as ex:
            detail = str(ex)
            if "не найдена" in detail:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Родительская задача не найдена или неверная структура",
                )
            elif "приоритет" in detail:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный приоритет. Допустимые значения: low, medium, high",
                )
            raise


async def update_task(
    task_id: UUID,
    task_update: TaskUpdateSheme,
    data_manager: DataManager,
) -> TaskOutSheme:
    """
    Обновление задачи через TaskService.

    Аргументы:
        task_id (UUID): ID задачи.
        task_update (TaskUpdateSheme): Обновляемые данные.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskOutSheme: Обновлённая задача.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Не валидирует права — делается в `handlers.py`.

    Возможные исключения:
        HTTPException: 404, если задача не найдена.
    """
    async with data_manager() as uow:
        task_service = TaskService()
        try:
            task = await task_service.update_task(
                task_repo=uow.tasks,
                task_id=task_id,
                name=task_update.name,
                description=task_update.description,
                priority=task_update.priority,
            )
            return TaskOutSheme.model_validate(task)
        except TaskNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


async def delete_task(
    task_id: UUID,
    data_manager: DataManager,
) -> None:
    """
    Удаление задачи через TaskService.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DataManager): Внедрённый менеджер данных.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если задача не найдена.
    """
    async with data_manager() as uow:
        task_service = TaskService()
        try:
            await task_service.delete_task(
                task_repo=uow.tasks,
                task_id=task_id,
            )
        except TaskNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )



async def add_executor_to_task(
    task_id: UUID,
    executor_data: Annotated[AddExecutor, ...],
    data_manager: DataManager,
):
    """
    Добавление исполнителя к задаче через TaskService.

    Аргументы:
        task_id (UUID): ID задачи.
        executor_data (AddExecutor): Данные исполнителя (`user_id`, `estimate`).
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskExecutorOutSheme: Созданная связка `task_id`, `user_id`, `estimate`.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация прав: `user_id` проверяется в `handlers.py`.

    Возможные исключения:
        HTTPException: 404, если задача не найдена.
        HTTPException: 409, если исполнитель уже добавлен.
    """
    async with data_manager() as uow:
        task_service = TaskService()
        try:
            executor = await task_service.add_executor(
                task_repo=uow.tasks,
                task_executor_repo=uow.task_executors,
                task_id=task_id,
                user_id=executor_data.user_id,
                estimate=executor_data.estimate,
            )
            return TaskExecutorOutSheme.model_validate(executor)
        except TaskNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )
        except Exception as ex:
            if "уже добавлен" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Исполнитель уже добавлен к задаче",
                )
            raise


async def update_executor_estimate(
    task_id: UUID,
    user_id: UUID,
    estimate: Annotated[int, ...],
    data_manager: DataManager,
):
    """
    Обновление оценки исполнителя через TaskService.

    Аргументы:
        task_id (UUID): ID задачи.
        user_id (UUID): ID пользователя-исполнителя.
        estimate (int): Новая оценка (не может быть отрицательной).
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskExecutorOutSheme: Обновлённая связка.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация оценки: `estimate >= 0` (через Pydantic, но здесь — явная проверка).
        - Валидация прав: `user_id` проверяется в `handlers.py`.

    Возможные исключения:
        HTTPException: 404, если связка не найдена.
    """
    # Валидация оценки (защита от отрицательных значений)
    if estimate < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Оценка не может быть отрицательной",
        )

    async with data_manager() as uow:
        task_service = TaskService()
        try:
            executor = await task_service.update_executor_estimate(
                task_executor_repo=uow.task_executors,
                task_id=task_id,
                user_id=user_id,
                estimate=estimate,
            )
            return TaskExecutorOutSheme.model_validate(executor)
        except Exception as ex:
            if "не найдена" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Связка задача-исполнитель не найдена",
                )
            raise
