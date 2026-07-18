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

from datetime import timedelta
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.src.api.api_utils import DependsDataManager
from app.src.api.exceptions import EventNotFound, MeetingNotFound
from app.src.api.services.event_service import EventService, MeetingService
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
async def create_event(
    event_data: Annotated[EventCreate, ...],
    user_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Создание события через EventService.

    Аргументы:
        event_data (EventCreate): Данные события.
        user_id (UUID): ID пользователя (из токена, валидация в handlers).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        EventSheme: Созданное событие.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация `start_datetime < end_datetime` в сервисе.

    Возможные исключения:
        HTTPException: 400, если временные интервалы некорректны.
        HTTPException: 404, если пользователь не найден.
    """
    async with data_manager() as uow:
        event_service = EventService()
        try:
            event = await event_service.create_event(
                event_repo=uow.events,
                user_repo=uow.users,
                user_id=user_id,
                name=event_data.name,
                description=event_data.description,
                start_datetime=event_data.start_datetime,
                end_datetime=event_data.end_datetime,
            )
            return event
        except ValueError as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ex),
            )
        except EventNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


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
async def get_event_by_id(
    event_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Получение события по ID через кэшированный Unit of Work.

    Аргументы:
        event_id (UUID): ID события.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        EventSheme: Событие.

    Дополнительная информация:
        - Кэширование TTL: 10 минут.
        - Используется `uow.events.get_by_id`.

    Возможные исключения:
        HTTPException: 404, если событие не найдено.
    """
    async with data_manager.cache(timedelta(minutes=10)) as cuow:
        event = await cuow.events.get_by_id(event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Событие не найдено",
            )

        return EventSheme.model_validate(event)


# —————— 3. GET /users/{user_id}/events — события пользователя — кэшировано ——————


@event_router.get(
    "/users/{user_id}/events",
    response_model=List[EventSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить все события пользователя",
    description="Возвращает события пользователя с пагинацией. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список событий (может быть пустым)"},
        404: {"description": "Пользователь не найден"},
    },
)
async def get_events_for_user(
    user_id: UUID,
    data_manager: DependsDataManager,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Количество записей на страницу")
    ] = 10,
):
    """
    Получение событий пользователя через кэшированный Unit of Work.

    Аргументы:
        user_id (UUID): ID пользователя.
        page (int): Номер страницы (по умолчанию 1).
        page_size (int): Размер страницы (по умолчанию 10).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        list[EventSheme]: Список событий.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется `uow.events.get_all_paginated`.

    Возможные исключения:
        HTTPException: 404, если пользователь не найден (через сервис).
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        event_service = EventService()
        try:
            events, _ = await event_service.get_events_for_user(
                event_repo=cuow.events,
                user_id=user_id,
                page=page,
                page_size=page_size,
            )
            return events
        except EventNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )


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
async def update_event(
    event_id: UUID,
    event_update: Annotated[EventCreate, ...],
    data_manager: DependsDataManager,
):
    """
    Обновление события через EventService.

    Аргументы:
        event_id (UUID): ID события.
        event_update (EventCreate): Обновляемые данные.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        EventSheme: Обновлённое событие.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если событие не найдено.
        HTTPException: 400, если временные интервалы некорректны.
    """
    async with data_manager() as uow:
        event_service = EventService()
        try:
            event = await event_service.update_event(
                event_repo=uow.events,
                event_id=event_id,
                name=event_update.name,
                description=event_update.description,
                start_datetime=event_update.start_datetime,
                end_datetime=event_update.end_datetime,
            )
            return event
        except ValueError as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ex),
            )
        except EventNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


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
async def delete_event(
    event_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Удаление события через EventService.

    Аргументы:
        event_id (UUID): ID события.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если событие не найдено.
    """
    async with data_manager() as uow:
        event_service = EventService()
        try:
            await event_service.delete_event(
                event_repo=uow.events,
                event_id=event_id,
            )
            return None  # FastAPI автоматически вернёт 204
        except EventNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


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
async def create_meeting(
    meeting_data: Annotated[MeetingCreate, ...],
    team_id: UUID,  # получено из токена или body
    data_manager: DependsDataManager,
):
    """
    Создание встречи через MeetingService.

    Аргументы:
        meeting_data (MeetingCreate): Данные встречи.
        team_id (UUID): ID команды.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        MeetingSheme: Созданная встреча.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация `start_datetime < end_datetime` в сервисе.

    Возможные исключения:
        HTTPException: 400, если временные интервалы некорректны.
        HTTPException: 404, если команда не найдена.
    """
    async with data_manager() as uow:
        meeting_service = MeetingService()
        try:
            meeting = await meeting_service.create_meeting(
                meeting_repo=uow.meetings,
                team_repo=uow.teams,
                team_id=team_id,
                name=meeting_data.name,
                description=meeting_data.description,
                start_datetime=meeting_data.start_datetime,
                end_datetime=meeting_data.end_datetime,
            )
            return meeting
        except ValueError as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ex),
            )
        except MeetingNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


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
async def get_meeting_by_id(
    meeting_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Получение встречи по ID через кэшированный Unit of Work.

    Аргументы:
        meeting_id (UUID): ID встречи.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        MeetingSheme: Встреча.

    Дополнительная информация:
        - Кэширование TTL: 10 минут.
        - Используется `uow.meetings.get_by_id`.

    Возможные исключения:
        HTTPException: 404, если встреча не найдена.
    """
    async with data_manager.cache(timedelta(minutes=10)) as cuow:
        meeting = await cuow.meetings.get_by_id(meeting_id)
        if meeting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Встреча не найдена",
            )

        return MeetingSheme.model_validate(meeting)


# —————— 8. GET /teams/{team_id}/meetings — встречи команды — кэшировано ——————


@meeting_router.get(
    "/teams/{team_id}/meetings",
    response_model=List[MeetingSheme],
    status_code=status.HTTP_200_OK,
    summary="Получить все встречи команды",
    description="Возвращает встречи команды с пагинацией. Данные кэшируются в Redis на 5 минут.",
    responses={
        200: {"description": "Список встреч (может быть пустым)"},
        404: {"description": "Команда не найдена"},
    },
)
async def get_meetings_for_team(
    team_id: UUID,
    data_manager: DependsDataManager,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Количество записей на страницу")
    ] = 10,
):
    """
    Получение встреч команды через кэшированный Unit of Work.

    Аргументы:
        team_id (UUID): ID команды.
        page (int): Номер страницы (по умолчанию 1).
        page_size (int): Размер страницы (по умолчанию 10).
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        list[MeetingSheme]: Список встреч.

    Дополнительная информация:
        - Кэширование TTL: 5 минут.
        - Используется `uow.meetings.get_all_paginated`.

    Возможные исключения:
        HTTPException: 404, если команда не найдена (через сервис).
    """
    async with data_manager.cache(timedelta(minutes=5)) as cuow:
        meeting_service = MeetingService()
        try:
            meetings, _ = await meeting_service.get_meetings_for_team(
                meeting_repo=cuow.meetings,
                team_id=team_id,
                page=page,
                page_size=page_size,
            )
            return meetings
        except MeetingNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


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
async def update_meeting(
    meeting_id: UUID,
    meeting_update: Annotated[MeetingCreate, ...],
    data_manager: DependsDataManager,
):
    """
    Обновление встречи через MeetingService.

    Аргументы:
        meeting_id (UUID): ID встречи.
        meeting_update (MeetingCreate): Обновляемые данные.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        MeetingSheme: Обновлённая встреча.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если встреча не найдена.
        HTTPException: 400, если временные интервалы некорректны.
    """
    async with data_manager() as uow:
        meeting_service = MeetingService()
        try:
            meeting = await meeting_service.update_meeting(
                meeting_repo=uow.meetings,
                meeting_id=meeting_id,
                name=meeting_update.name,
                description=meeting_update.description,
                start_datetime=meeting_update.start_datetime,
                end_datetime=meeting_update.end_datetime,
            )
            return meeting
        except ValueError as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ex),
            )
        except MeetingNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )


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
async def delete_meeting(
    meeting_id: UUID,
    data_manager: DependsDataManager,
):
    """
    Удаление встречи через MeetingService.

    Аргументы:
        meeting_id (UUID): ID встречи.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если встреча не найдена.
    """
    async with data_manager() as uow:
        meeting_service = MeetingService()
        try:
            await meeting_service.delete_meeting(
                meeting_repo=uow.meetings,
                meeting_id=meeting_id,
            )
            return None  # FastAPI автоматически вернёт 204
        except MeetingNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )
