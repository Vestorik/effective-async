"""
Обработчики (Handlers) для управления исполнителями задач (TaskExecutors).

Этот модуль содержит бизнес-логику и взаимодействие с сервисами/БД.
Вызывается из API-слоя (app.src.api.client.api.task_executor_api).

Функции:
    add_executor_to_task — добавление исполнителя к задаче.
    remove_executor_from_task — удаление исполнителя из задачи.
    update_executor_estimate_handler — обновление оценки исполнителя.
    get_executors_for_task_handler — получение списка исполнителей задачи.
    get_tasks_for_user_handler — получение задач пользователя.
"""

from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException, status

from app.src.api.utils.api_utils import DataManager
from app.src.api.exceptions import TaskNotFound, UserNotFound
from app.src.api.services.task_executor_service import TaskExecutorService
from app.src.api.shems import (
    AddExecutor,
    TaskExecutorOutSheme,
    TaskOutSheme,
)


async def add_executor_to_task(
    task_id: UUID,
    executor_data: AddExecutor,
    data_manager: DataManager,
) -> TaskExecutorOutSheme:
    """
    Добавление исполнителя к задаче через TaskExecutorService.

    Аргументы:
        task_id (UUID): ID задачи.
        executor_data (AddExecutor): Данные исполнителя (`user_id`, `estimate`).
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskExecutorOutSheme: Созданная связка `task_id`, `user_id`, `estimate`.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Используется обычный Unit of Work.
        - Валидация прав (разрешения на добавление исполнителя) должна быть реализована
          в сервисе или проверена вызывающим кодом до вызова этого хендлера,
          если это требуется бизнес-логикой (здесь проверяется существование сущностей).

    Возможные исключения:
        HTTPException: 404, если задача или пользователь не найдены.
        HTTPException: 409, если исполнитель уже добавлен к задаче.
    """
    async with data_manager() as uow:
        task_executor_service = TaskExecutorService()
        try:
            executor = await task_executor_service.add_executor(
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
        except UserNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )
        except Exception as ex:
            if "уже добавлен" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Исполнитель уже добавлен к задаче",
                )
            raise


async def remove_executor_from_task(
    task_id: UUID,
    user_id: UUID,
    data_manager: DataManager,
) -> None:
    """
    Удаление исполнителя из задачи через TaskExecutorService.

    Аргументы:
        task_id (UUID): ID задачи.
        user_id (UUID): ID пользователя-исполнителя.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        None: Операция удаления не возвращает данные.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Используется обычный Unit of Work.

    Возможные исключения:
        HTTPException: 404, если связка задача-исполнитель не найдена.
    """
    async with data_manager() as uow:
        task_executor_service = TaskExecutorService()
        try:
            await task_executor_service.remove_executor(
                task_executor_repo=uow.task_executors,
                task_id=task_id,
                user_id=user_id,
            )
        except Exception as ex:
            if "не найдена" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Связка задача-исполнитель не найдена",
                )
            raise


async def update_executor_estimate_handler(
    task_id: UUID,
    user_id: UUID,
    estimate: int,
    data_manager: DataManager,
) -> TaskExecutorOutSheme:
    """
    Обновление оценки исполнителя через TaskExecutorService.

    Аргументы:
        task_id (UUID): ID задачи.
        user_id (UUID): ID пользователя-исполнителя.
        estimate (int): Новая оценка (не может быть отрицательной).
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskExecutorOutSheme: Обновлённая связка.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Используется обычный Unit of Work.
        - Валидация `estimate >= 0` выполняется на уровне API (Query параметр).

    Возможные исключения:
        HTTPException: 404, если связка задача-исполнитель не найдена.
    """
    async with data_manager() as uow:
        task_executor_service = TaskExecutorService()
        try:
            executor = await task_executor_service.update_estimate(
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


async def get_executors_for_task_handler(
    task_id: UUID,
    data_manager: DataManager,
) -> list[TaskExecutorOutSheme]:
    """
    Получение всех исполнителей задачи через кэшированный Unit of Work.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        List[TaskExecutorOutSheme]: Список исполнителей.

    Дополнительная информация:
        - Кэширование TTL: 10 минут.
        - Используется кэшированный Unit of Work (CachedUnitOfWork).
        - Используется `task_executor_service.get_executors_for_task`.

    Возможные исключения:
        HTTPException: 404, если задача не найдена (через сервис).
    """
    async with data_manager.cache(timedelta(minutes=10)) as cuow:
        task_executor_service = TaskExecutorService()
        try:
            executors = await task_executor_service.get_executors_for_task(
                task_executor_repo=cuow.task_executors,
                task_id=task_id,
            )
            return executors
        except TaskNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


async def get_tasks_for_user_handler(
    user_id: UUID,
    data_manager: DataManager,
    page: int = 1,
    page_size: int = 10,
) -> Sequence[TaskOutSheme]:
    """
    Получение всех задач пользователя с пагинацией через кэшированный Unit of Work.

    Аргументы:
        user_id (UUID): ID пользователя.
        data_manager (DataManager): Внедрённый менеджер данных.
        page (int): Номер страницы (по умолчанию 1).
        page_size (int): Размер страницы (по умолчанию 10).

    Возвращает:
        Sequence[TaskOutSheme]: Список задач на странице.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется кэшированный Unit of Work (CachedUnitOfWork).
        - Используется `task_executor_service.get_tasks_for_user`.

    Возможные исключения:
        HTTPException: 404, если пользователь не найден (через сервис).
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        task_executor_service = TaskExecutorService()
        try:
            tasks, _ = await task_executor_service.get_tasks_for_user(
                task_executor_repo=cuow.task_executors,
                user_id=user_id,
                page=page,
                page_size=page_size,
            )
            return [TaskOutSheme.model_validate(task) for task in tasks]
        except Exception as ex:
            if "не найден" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден",
                )
            raise