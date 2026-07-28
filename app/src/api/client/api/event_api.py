# app/src/api/routes/events.py
"""
Эндпоинты управления событиями (Events) и встречами (Meetings).

Роуты:
    События:
        POST /events — создание события (дедлайн, напоминание)
        GET /events/{event_id} — получение события по ID (кэш 10 мин)
        GET /users/{user_id}/events — события пользователя с пагинацией (кэш 5 мин)
        PATCH /events/{event_id} — обновление события
        DELETE /events/{event_id} — удаление события

    Встречи:
        POST /meetings — создание встречи
        GET /meetings/{meeting_id} — получение встречи по ID (кэш 10 мин)
        GET /teams/{team_id}/meetings — встречи команды с пагинацией (кэш 5 мин)
        PATCH /meetings/{meeting_id} — обновление встречи
        DELETE /meetings/{meeting_id} — удаление встречи

Правила:
    - Для чтения используем `CachedUnitOfWork` с TTL.
    - Для записи — обычный `UnitOfWork`.
    - Валидация прав (team member/admin) делается в handlers.
    - Все исключения привязаны к `app.src.api.exceptions`.
    - Используем `DependsDataManager` для инъекции `DataManager`.
    - Возвращаем только безопасные схемы (`EventSheme`, `MeetingSheme`).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.src.api.api_utils import DependsDataManager
from app.src.api.handlers.event_handlers import (
    create_event,
    create_meeting,
    delete_event,
    delete_meeting,
    get_event_by_id,
    get_events_for_user,
    get_meeting_by_id,
    get_meetings_for_team,
    update_event,
    update_meeting,
)
from app.src.api.shems import EventCreate, EventSheme, MeetingCreate, MeetingSheme

event_router = APIRouter(prefix="/events", tags=["События"])
meeting_router = APIRouter(prefix="/meetings", tags=["Встречи"])


# —————— 1. POST /events — создание события ——————


@event_router.post(
    "",
    response_model=EventSheme,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новое событие",
    description="Создаёт событие (дедлайн, напоминание). Валидирует start_datetime < end_datetime.",
    responses={
        201: {"description": "Событие успешно создано"},
        400: {"description": "Некорректные временные интервалы"},
        404: {"description": "Пользователь не найден"},
    },
)
async def create_event_api(
    event_data: Annotated[EventCreate, ...],
    user_id: UUID,
    data_manager: DependsDataManager,
):
    return await create_event(event_data, user_id, data_manager)


# —————— 2. GET /events/{event_id} — кэшированный GET ——————


@event_router.get(
    "/{event_id}",
    response_model=EventSheme,
    status_code=status.HTTP_200_OK,
    summary="Получить событие по ID",
    description="Возвращает событие с указанным ID. Данные кэшируются в Redis на 10 минут.",
    responses={
        200: {"description": "Событие найдено"},
        404: {"description": "Событие не найдено"},
    },
)
async def get_event_by_id_api(
    event_id: UUID,
    data_manager: DependsDataManager,
):
    return await get_event_by_id(event_id, data_manager)


# —————— 3. GET /users/{user_id}/events — события пользователя — кэшировано ——————


@event_router.get(
    "/users/{user_id}/events",
    response_model=list[EventSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить все события пользователя",
    description="Возвращает события пользователя с пагинацией. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список событий (может быть пустым)"},
        404: {"description": "Пользователь не найден"},
    },
)
async def get_events_for_user_api(
    user_id: UUID,
    data_manager: DependsDataManager,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Количество записей на страницу")
    ] = 10,
):
    return await get_events_for_user(user_id, data_manager, page, page_size)


# —————— 4. PATCH /events/{event_id} — обновление события ——————


@event_router.patch(
    "/{event_id}",
    response_model=EventSheme,
    status_code=status.HTTP_200_OK,
    summary="Частичное обновление события",
    description="Обновляет название, описание, временные метки события. Не кэшируется (изменяет состояние).",
    responses={
        200: {"description": "Событие успешно обновлено"},
        404: {"description": "Событие не найдено"},
        400: {"description": "Некорректные временные интервалы"},
    },
)
async def update_event_api(
    event_id: UUID,
    event_update: Annotated[EventCreate, ...],
    data_manager: DependsDataManager,
):
    return await update_event(event_id, event_update, data_manager)


# —————— 5. DELETE /events/{event_id} — удаление события ——————


@event_router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить событие",
    description="Удаляет событие по ID. Не кэшируется (изменяет состояние).",
    responses={
        204: {"description": "Событие удалено"},
        404: {"description": "Событие не найдено"},
    },
)
async def delete_event_api(
    event_id: UUID,
    data_manager: DependsDataManager,
):
    await delete_event(event_id, data_manager)


# —————— 6. POST /meetings — создание встречи ——————


@meeting_router.post(
    "",
    response_model=MeetingSheme,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую встречу",
    description="Создаёт встречу для команды. Валидирует start_datetime < end_datetime.",
    responses={
        201: {"description": "Встреча успешно создана"},
        400: {"description": "Некорректные временные интервалы"},
        404: {"description": "Команда не найдена"},
    },
)
async def create_meeting_api(
    meeting_data: Annotated[MeetingCreate, ...],
    team_id: UUID,  # получено из токена или body
    data_manager: DependsDataManager,
):
    return await create_meeting(meeting_data, team_id, data_manager)


# —————— 7. GET /meetings/{meeting_id} — кэшированный GET ——————


@meeting_router.get(
    "/{meeting_id}",
    response_model=MeetingSheme,
    status_code=status.HTTP_200_OK,
    summary="Получить встречу по ID",
    description="Возвращает встречу с указанным ID. Данные кэшируются в Redis на 10 минут.",
    responses={
        200: {"description": "Встреча найдена"},
        404: {"description": "Встреча не найдена"},
    },
)
async def get_meeting_by_id_api(
    meeting_id: UUID,
    data_manager: DependsDataManager,
):
    return await get_meeting_by_id(meeting_id, data_manager)


# —————— 8. GET /teams/{team_id}/meetings — встречи команды — кэшировано ——————


@meeting_router.get(
    "/teams/{team_id}/meetings",
    response_model=list[MeetingSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить все встречи команды",
    description="Возвращает встречи команды с пагинацией. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список встреч (может быть пустым)"},
        404: {"description": "Команда не найдена"},
    },
)
async def get_meetings_for_team_api(
    team_id: UUID,
    data_manager: DependsDataManager,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Количество записей на страницу")
    ] = 10,
):
    return await get_meetings_for_team(team_id, data_manager, page, page_size)


# —————— 9. PATCH /meetings/{meeting_id} — обновление встречи ——————


@meeting_router.patch(
    "/{meeting_id}",
    response_model=MeetingSheme,
    status_code=status.HTTP_200_OK,
    summary="Частичное обновление встречи",
    description="Обновляет название, описание, временные метки встречи. Не кэшируется (изменяет состояние).",
    responses={
        200: {"description": "Встреча успешно обновлена"},
        404: {"description": "Встреча не найдена"},
        400: {"description": "Некорректные временные интервалы"},
    },
)
async def update_meeting_api(
    meeting_id: UUID,
    meeting_update: Annotated[MeetingCreate, ...],
    data_manager: DependsDataManager,
):
    return await update_meeting(meeting_id, meeting_update, data_manager)


# —————— 10. DELETE /meetings/{meeting_id} — удаление встречи ——————


@meeting_router.delete(
    "/{meeting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить встречу",
    description="Удаляет встречу по ID. Не кэшируется (изменяет состояние).",
    responses={
        204: {"description": "Встреча удалена"},
        404: {"description": "Встреча не найдена"},
    },
)
async def delete_meeting_api(
    meeting_id: UUID,
    data_manager: DependsDataManager,
):
    await delete_meeting(meeting_id, data_manager)
