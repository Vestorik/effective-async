# app/src/api/routes/task_executors.py
"""
Эндпоинты управления исполнителями задач (TaskExecutors).

Роуты:
    POST /tasks/{task_id}/executors — добавить исполнителя
    DELETE /tasks/{task_id}/executors/{user_id} — удалить исполнителя
    PATCH /tasks/{task_id}/executors/{user_id} — обновить оценку исполнителя
    GET /tasks/{task_id}/executors — получить всех исполнителей задачи (кэш 10 мин)
    GET /users/{user_id}/tasks — получить все задачи пользователя (кэш 5 мин)

Правила:
    - Для чтения используем `CachedUnitOfWork` с TTL.
    - Для записи — обычный `UnitOfWork`.
    - Валидация прав (manager/admin) делается в handlers (здесь — `user_id` из токена).
    - Все исключения привязаны к `app.src.api.exceptions`.
    - Используем `DependsDataManager` для инъекции `DataManager`.
    - Возвращаем только безопасные схемы (`TaskExecutorOutSheme`).
"""


from typing import Sequence
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from datetime import timedelta

from app.src.api.api_utils import DependsDataManager
from app.src.api.exceptions import TaskNotFound, UserNotFound
from app.src.api.services.task_executor_service import TaskExecutorService
from app.src.api.shems import (
    AddExecutor,
    TaskExecutorOutSheme,
    TaskOutSheme,
)

task_executor_router = APIRouter(prefix="/tasks/{task_id}/executors", tags=["Исполнители задач"])


# —————— 1. POST /tasks/{task_id}/executors — добавить исполнителя ——————

@task_executor_router.post(
    "",
    response_model=TaskExecutorOutSheme,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить исполнителя к задаче",
    description="Добавляет пользователя как исполнителя задачи. Может указать оценку (estimate).",
    responses={
        201: {"description": "Исполнитель успешно добавлен"},
        404: {"description": "Задача или пользователь не найдены"},
        409: {"description": "Исполнитель уже добавлен к задаче"},
    },
)
async def add_executor(
    task_id: UUID,
    executor_data: Annotated[AddExecutor, ...],
    data_manager: DependsDataManager,
):
    """
    Добавление исполнителя к задаче через TaskExecutorService.

    Аргументы:
        task_id (UUID): ID задачи.
        executor_data (AddExecutor): Данные исполнителя (`user_id`, `estimate`).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskExecutorOutSheme: Созданная связка `task_id`, `user_id`, `estimate`.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация прав: `user_id` проверяется в `handlers.py`.

    Возможные исключения:
        HTTPException: 404, если задача или пользователь не найдены.
        HTTPException: 409, если исполнитель уже добавлен.
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


# —————— 2. DELETE /tasks/{task_id}/executors/{user_id} — удалить исполнителя ——————

@task_executor_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить исполнителя из задачи",
    description="Удаляет исполнителя из задачи. Не кэшируется (изменяет состояние).",
    responses={
        204: {"description": "Исполнитель успешно удалён"},
        404: {"description": "Связка задача-исполнитель не найдена"},
    },
)
async def remove_executor(
    task_id: UUID,
    user_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Удаление исполнителя из задачи через TaskExecutorService.

    Аргументы:
        task_id (UUID): ID задачи.
        user_id (UUID): ID пользователя-исполнителя.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если связка не найдена.
    """
    async with data_manager() as uow:
        task_executor_service = TaskExecutorService()
        try:
            await task_executor_service.remove_executor(
                task_executor_repo=uow.task_executors,
                task_id=task_id,
                user_id=user_id,
            )
            return None  # FastAPI автоматически вернёт 204
        except Exception as ex:
            if "не найдена" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Связка задача-исполнитель не найдена",
                )
            raise


# —————— 3. PATCH /tasks/{task_id}/executors/{user_id} — обновить оценку ——————

@task_executor_router.patch(
    "/{user_id}",
    response_model=TaskExecutorOutSheme,
    status_code=status.HTTP_200_OK,
    summary="Обновить оценку исполнителя",
    description="Обновляет оценку (estimate) исполнителя для задачи. Не кэшируется (изменяет состояние).",
    responses={
        200: {"description": "Оценка успешно обновлена"},
        404: {"description": "Связка задача-исполнитель не найдена"},
    },
)
async def update_executor_estimate(
    task_id: UUID,
    user_id: UUID,
    estimate: Annotated[int, Query(..., ge=0, description="Оценка (не может быть отрицательной)")],
    data_manager: DependsDataManager,
):
    """
    Обновление оценки исполнителя через TaskExecutorService.

    Аргументы:
        task_id (UUID): ID задачи.
        user_id (UUID): ID пользователя-исполнителя.
        estimate (int): Новая оценка (не может быть отрицательной).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskExecutorOutSheme: Обновлённая связка.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация через Pydantic: `Query(..., ge=0)`.

    Возможные исключения:
        HTTPException: 404, если связка не найдена.
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


# —————— 4. GET /tasks/{task_id}/executors — список исполнителей — кэшировано ——————

@task_executor_router.get(
    "",
    response_model=List[TaskExecutorOutSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить всех исполнителей задачи",
    description="Возвращает список всех исполнителей задачи. Данные кэшируются в Redis на 10 минут.",
    responses={
        200: {"description": "Список исполнителей (может быть пустым)"},
        404: {"description": "Задача не найдена"},
    },
)
async def get_executors_for_task(
    task_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Получение всех исполнителей задачи через кэшированный Unit of Work.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        list[TaskExecutorOutSheme]: Список исполнителей.

    Дополнительная информация:
        - Кэширование TTL: 10 минут.
        - Используется `uow.task_executors.get_executors_for_task`.

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


# —————— 5. GET /users/{user_id}/tasks — список задач пользователя — кэшировано ——————


user_tasks_router = APIRouter(prefix="/users/{user_id}/tasks", tags=["Задачи пользователя"])


@user_tasks_router.get(
    "",
    response_model=Sequence[TaskOutSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить все задачи пользователя",
    description="Возвращает список задач, за которые отвечает пользователь. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список задач (может быть пустым)"},
        404: {"description": "Пользователь не найден"},
    },
)
async def get_tasks_for_user(
    data_manager: DependsDataManager,
    user_id: UUID,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Количество записей на страницу")] = 10,
):
    """
    Получение всех задач пользователя с пагинацией через кэшированный Unit of Work.

    Аргументы:
        user_id (UUID): ID пользователя.
        page (int): Номер страницы (по умолчанию 1).
        page_size (int): Размер страницы (по умолчанию 10).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        list[TaskOutSheme]: Список задач на странице.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется `uow.task_executors.get_tasks_for_user`.

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

