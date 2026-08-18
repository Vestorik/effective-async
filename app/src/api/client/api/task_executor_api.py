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


from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.src.api.utils.api_utils import DependsDataManager
from app.src.api.handlers.task_executor_handlers import (
    add_executor_to_task,
    get_executors_for_task_handler,
    get_tasks_for_user_handler,
    remove_executor_from_task,
    update_executor_estimate_handler,
)
from app.src.api.shems import (
    AddExecutor,
    TaskExecutorOutSheme,
    TaskOutSheme,
)

task_executor_router = APIRouter(prefix="/tasks/{task_id}/executors", tags=["Исполнители задач"])



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
async def add_executor_api(
    task_id: UUID,
    executor_data: Annotated[AddExecutor, ...],
    data_manager: DependsDataManager,
):
    """
    API-обёртка для добавления исполнителя.

    Аргументы:
        task_id (UUID): ID задачи.
        executor_data (AddExecutor): Данные исполнителя.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskExecutorOutSheme: Созданная связка.
    """
    return await add_executor_to_task(task_id, executor_data, data_manager)


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
async def remove_executor_api(
    task_id: UUID,
    user_id: UUID,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для удаления исполнителя.

    Аргументы:
        task_id (UUID): ID задачи.
        user_id (UUID): ID пользователя-исполнителя.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        None: Пустой ответ со статусом 204.
    """
    return await remove_executor_from_task(task_id, user_id, data_manager)


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
async def update_executor_estimate_api(
    task_id: UUID,
    user_id: UUID,
    estimate: Annotated[int, Query(..., ge=0, description="Оценка (не может быть отрицательной)")],
    data_manager: DependsDataManager,
):
    """
    API-обёртка для обновления оценки исполнителя.

    Аргументы:
        task_id (UUID): ID задачи.
        user_id (UUID): ID пользователя-исполнителя.
        estimate (int): Новая оценка.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskExecutorOutSheme: Обновлённая связка.
    """
    return await update_executor_estimate_handler(task_id, user_id, estimate, data_manager)


@task_executor_router.get(
    "",
    response_model=list[TaskExecutorOutSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить всех исполнителей задачи",
    description="Возвращает список всех исполнителей задачи. Данные кэшируются в Redis на 10 минут.",
    responses={
        200: {"description": "Список исполнителей (может быть пустым)"},
        404: {"description": "Задача не найдена"},
    },
)
async def get_executors_for_task_api(
    task_id: UUID,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для получения исполнителей задачи.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        List[TaskExecutorOutSheme]: Список исполнителей.
    """
    return await get_executors_for_task_handler(task_id, data_manager)


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
async def get_tasks_for_user_api(
    user_id: UUID,
    data_manager: DependsDataManager,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Количество записей на страницу")] = 10,
):
    """
    API-обёртка для получения задач пользователя.

    Аргументы:
        user_id (UUID): ID пользователя.
        data_manager (DependsDataManager): Внедрённый менеджер данных.
        page (int): Номер страницы.
        page_size (int): Размер страницы.

    Возвращает:
        Sequence[TaskOutSheme]: Список задач.
    """
    return await get_tasks_for_user_handler(user_id, data_manager, page, page_size)

