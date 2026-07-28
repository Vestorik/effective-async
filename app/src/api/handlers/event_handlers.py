# app/src/api/routes/events.py
"""
Обработчики управления событиями (Events) и встречами (Meetings).

Правила:
    - Для чтения используем `CachedUnitOfWork` с TTL.
    - Для записи — обычный `UnitOfWork`.
    - Валидация прав (team member/admin) делается в handlers.
    - Все исключения привязаны к `app.src.api.exceptions`.
    - Используем `DataManager` для инъекции `DataManager`.
    - Возвращаем только безопасные схемы (`EventSheme`, `MeetingSheme`).
"""

from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.src.api.exceptions import EventNotFound, MeetingNotFound
from app.src.api.services.event_service import EventService, MeetingService
from app.src.api.shems import EventCreate, EventSheme, MeetingCreate, MeetingSheme
from app.src.dal.main import DataManager

event_router = APIRouter(prefix="/events", tags=["События"])
meeting_router = APIRouter(prefix="/meetings", tags=["Встречи"])


# —————— 1. POST /events — создание события ——————


async def create_event(
    event_data: Annotated[EventCreate, ...],
    user_id: UUID,
    data_manager: DataManager,
):
    """
    Создание события через EventService.

    Аргументы:
        event_data (EventCreate): Данные события.
        user_id (UUID): ID пользователя (из токена, валидация в handlers).
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def get_event_by_id(
    event_id: UUID,
    data_manager: DataManager,
):
    """
    Получение события по ID через кэшированный Unit of Work.

    Аргументы:
        event_id (UUID): ID события.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def get_events_for_user(
    user_id: UUID,
    data_manager: DataManager,
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
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def update_event(
    event_id: UUID,
    event_update: Annotated[EventCreate, ...],
    data_manager: DataManager,
):
    """
    Обновление события через EventService.

    Аргументы:
        event_id (UUID): ID события.
        event_update (EventCreate): Обновляемые данные.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def delete_event(
    event_id: UUID,
    data_manager: DataManager,
):
    """
    Удаление события через EventService.

    Аргументы:
        event_id (UUID): ID события.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def create_meeting(
    meeting_data: Annotated[MeetingCreate, ...],
    team_id: UUID,  # получено из токена или body
    data_manager: DataManager,
):
    """
    Создание встречи через MeetingService.

    Аргументы:
        meeting_data (MeetingCreate): Данные встречи.
        team_id (UUID): ID команды.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def get_meeting_by_id(
    meeting_id: UUID,
    data_manager: DataManager,
):
    """
    Получение встречи по ID через кэшированный Unit of Work.

    Аргументы:
        meeting_id (UUID): ID встречи.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def get_meetings_for_team(
    team_id: UUID,
    data_manager: DataManager,
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
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def update_meeting(
    meeting_id: UUID,
    meeting_update: Annotated[MeetingCreate, ...],
    data_manager: DataManager,
):
    """
    Обновление встречи через MeetingService.

    Аргументы:
        meeting_id (UUID): ID встречи.
        meeting_update (MeetingCreate): Обновляемые данные.
        data_manager (DataManager): Внедрённый менеджер данных.

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


async def delete_meeting(
    meeting_id: UUID,
    data_manager: DataManager,
) -> None:
    """
    Удаление встречи через MeetingService.

    Аргументы:
        meeting_id (UUID): ID встречи.
        data_manager (DataManager): Внедрённый менеджер данных.

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
