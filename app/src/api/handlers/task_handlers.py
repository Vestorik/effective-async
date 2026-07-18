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
    - Используем `DependsDataManager` для инъекции `DataManager`.
    - Возвращаем только безопасные схемы (`TaskOutSheme`, `TaskWithExecutorsSheme`).
"""

from datetime import timedelta
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.src.api.api_utils import DependsDataManager
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

task_router = APIRouter(prefix="/tasks", tags=["Задачи"])


# —————— 1. GET /tasks/{task_id} — кэшированный GET ——————


@task_router.get(
    "/{task_id}",
    response_model=TaskOutSheme,
    status_code=status.HTTP_200_OK,
    summary="Получить задачу по ID",
    description="Возвращает задачу с указанным ID. Данные кэшируются в Redis на 10 минут.",
    responses={
        200: {"description": "Задача найдена"},
        404: {"description": "Задача не найдена"},
    },
)
async def get_task_by_id(
    task_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Получение задачи по ID через кэшированный Unit of Work.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

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


# —————— 2. GET /teams/{team_id}/tasks — список задач команды — кэшировано ——————


@task_router.get(
    "/teams/{team_id}/tasks",
    response_model=List[TaskOutSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить все задачи команды",
    description="Возвращает список задач команды с пагинацией и фильтрацией по приоритету. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список задач (может быть пустым)"},
        404: {"description": "Команда не найдена"},
    },
)
async def get_team_tasks(
    team_id: UUID,
    data_manager: DependsDataManager,
    priority: Annotated[
        Optional[str], Query(description="Фильтр по приоритету: low, medium, high")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Количество записей на страницу")
    ] = 10,
):
    """
    Получение задач команды с фильтрацией по приоритету через кэшированный Unit of Work.

    Аргументы:
        team_id (UUID): ID команды.
        priority (Optional[str]): Фильтр по приоритету (`low`, `medium`, `high`).
        page (int): Номер страницы (по умолчанию 1).
        page_size (int): Размер страницы (по умолчанию 10).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        list[TaskOutSheme]: Список задач на странице.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется `uow.tasks.get_tasks_by_team_and_priority`.

    Возможные исключения:
        HTTPException: 404, если команда не найдена (проверка в сервисе, но здесь — как fallback).
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        tasks = await cuow.tasks.get_tasks_by_team_and_priority(team_id, priority)
        return [TaskOutSheme.model_validate(task) for task in tasks]


# —————— 3. POST /teams/{team_id}/tasks — создание задачи ——————


@task_router.post(
    "/teams/{team_id}/tasks",
    response_model=TaskCreateOutSheme,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую задачу",
    description="Создаёт задачу в команде. Может быть подзадачей другой задачи. Поддерживает добавление исполнителей.",
    responses={
        201: {"description": "Задача успешно создана"},
        404: {"description": "Команда или родительская задача не найдены"},
        400: {"description": "Неверный приоритет или структура подзадач"},
    },
)
async def create_task(
    team_id: UUID,
    task_data: Annotated[TaskCreate, ...],
    user_id: UUID,  # получено из JWT в handlers.py (см. ниже)
    data_manager: DependsDataManager,
):
    """
    Создание задачи через TaskService.

    Аргументы:
        team_id (UUID): ID команды.
        task_data (TaskCreate): Данные задачи.
        user_id (UUID): ID пользователя, создающего задачу (из токена, валидация в handlers).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

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
            if "не найдена" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Родительская задача не найдена или неверная структура",
                )
            elif "приоритет" in str(ex):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный приоритет. Допустимые значения: low, medium, high",
                )
            raise


# —————— 4. PATCH /tasks/{task_id} — частичное обновление ——————


@task_router.patch(
    "/{task_id}",
    response_model=TaskOutSheme,
    status_code=status.HTTP_200_OK,
    summary="Частичное обновление задачи",
    description="Обновляет название, описание, приоритет задачи. Не кэшируется (изменяет состояние).",
    responses={
        200: {"description": "Задача успешно обновлена"},
        404: {"description": "Задача не найдена"},
    },
)
async def update_task(
    task_id: UUID,
    task_update: Annotated[TaskUpdateSheme, ...],
    data_manager: DependsDataManager,
):
    """
    Обновление задачи через TaskService.

    Аргументы:
        task_id (UUID): ID задачи.
        task_update (TaskUpdateSheme): Обновляемые данные.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

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


# —————— 5. DELETE /tasks/{task_id} — удаление задачи ——————


@task_router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить задачу",
    description="Удаляет задачу по ID. Не кэшируется (изменяет состояние).",
    responses={
        204: {"description": "Задача удалена"},
        404: {"description": "Задача не найдена"},
    },
)
async def delete_task(
    task_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Удаление задачи через TaskService.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

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
            return None  # FastAPI автоматически вернёт 204
        except TaskNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


# —————— 6. POST /tasks/{task_id}/executors — добавить исполнителя ——————


@task_router.post(
    "/{task_id}/executors",
    response_model=TaskExecutorOutSheme,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить исполнителя к задаче",
    description="Добавляет пользователя как исполнителя задачи. Может указать оценку (estimate).",
    responses={
        201: {"description": "Исполнитель успешно добавлен"},
        404: {"description": "Задача не найдена"},
        409: {"description": "Исполнитель уже добавлен к задаче"},
    },
)
async def add_executor_to_task(
    task_id: UUID,
    executor_data: Annotated[AddExecutor, ...],
    data_manager: DependsDataManager,
):
    """
    Добавление исполнителя к задаче через TaskService.

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


# --- 7. PATCH /tasks/{task_id}/executors/{user_id} — обновить оценку исполнителя ---


@task_router.patch(
    "/{task_id}/executors/{user_id}",
    response_model=TaskExecutorOutSheme,
    status_code=status.HTTP_200_OK,
    summary="Обновить оценку исполнителя",
    description="Обновляет оценку (estimate) исполнителя для задачи.",
    responses={
        200: {"description": "Оценка успешно обновлена"},
        404: {"description": "Связка задача-исполнитель не найдена"},
    },
)
async def update_executor_estimate(
    task_id: UUID,
    user_id: UUID,
    estimate: Annotated[int, ...],
    data_manager: DependsDataManager,
):
    """
    Обновление оценки исполнителя через TaskService.

    Аргументы:
        task_id (UUID): ID задачи.
        user_id (UUID): ID пользователя-исполнителя.
        estimate (int): Новая оценка (не может быть отрицательной).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

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
