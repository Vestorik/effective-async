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
# app/src/api/client/api/task_api.py
"""
Эндпоинты управления задачами (Tasks).

Этот модуль определяет маршруты FastAPI.
Вся бизнес-логика делегируется модулю `app.src.api.handlers.task_handlers`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.src.api.api_utils import DependsDataManager
from app.src.api.handlers.task_handlers import (
    add_executor_to_task,
    create_task,
    delete_task,
    get_task_by_id,
    get_team_tasks,
    update_executor_estimate,
    update_task,
)
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
async def get_task_by_id_api(
    task_id: UUID,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для получения задачи по ID.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskOutSheme: Данные задачи.
    """
    return await get_task_by_id(task_id, data_manager)


# —————— 2. GET /teams/{team_id}/tasks — список задач команды — кэшировано ——————


@task_router.get(
    "/teams/{team_id}/tasks",
    response_model=list[TaskOutSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить все задачи команды",
    description="Возвращает список задач команды с пагинацией и фильтрацией по приоритету. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список задач (может быть пустым)"},
        404: {"description": "Команда не найдена"},
    },
)
async def get_team_tasks_api(
    team_id: UUID,
    data_manager: DependsDataManager,
    priority: Annotated[
        str | None, Query(description="Фильтр по приоритету: low, medium, high")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Количество записей на страницу")
    ] = 10,
):
    """
    API-обёртка для получения задач команды.

    Аргументы:
        team_id (UUID): ID команды.
        data_manager (DependsDataManager): Внедрённый менеджер данных.
        priority (Optional[str]): Фильтр по приоритету.
        page (int): Номер страницы.
        page_size (int): Размер страницы.

    Возвращает:
        List[TaskOutSheme]: Список задач.
    """
    return await get_team_tasks(team_id, data_manager, priority)


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
async def create_task_api(
    team_id: UUID,
    task_data: Annotated[TaskCreate, ...],
    user_id: UUID,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для создания задачи.

    Аргументы:
        team_id (UUID): ID команды.
        task_data (TaskCreate): Данные задачи.
        user_id (UUID): ID пользователя (из JWT).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskCreateOutSheme: Созданная задача.
    """
    return await create_task(team_id, task_data, user_id, data_manager)


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
async def update_task_api(
    task_id: UUID,
    task_update: Annotated[TaskUpdateSheme, ...],
    data_manager: DependsDataManager,
):
    """
    API-обёртка для обновления задачи.

    Аргументы:
        task_id (UUID): ID задачи.
        task_update (TaskUpdateSheme): Обновляемые данные.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        TaskOutSheme: Обновлённая задача.
    """
    return await update_task(task_id, task_update, data_manager)


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
async def delete_task_api(
    task_id: UUID,
    data_manager: DependsDataManager,
):
    """
    API-обёртка для удаления задачи.

    Аргументы:
        task_id (UUID): ID задачи.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        None: Пустой ответ со статусом 204.
    """
    return await delete_task(task_id, data_manager)


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
async def add_executor_to_task_api(
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
async def update_executor_estimate_api(
    task_id: UUID,
    user_id: UUID,
    estimate: Annotated[int, ...],
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
    return await update_executor_estimate(task_id, user_id, estimate, data_manager)