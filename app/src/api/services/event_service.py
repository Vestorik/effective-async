"""
Сервис управления событиями.

Методы:
    create_event: создаёт новое событие (дедлайн, напоминание).
    get_events_for_user: получает события пользователя с пагинацией.
    update_event: обновляет событие.
    delete_event: удаляет событие.

Ограничения:
    - Проверка прав (team member/admin) делается в handlers.
"""

from datetime import datetime, timezone
from logging import getLogger
from typing import List, Tuple
from uuid import UUID
from app.src.api.services.base_services import BaseService
from app.src.api.exceptions import EventNotFound, MeetingNotFound
from app.src.api.shems import EventSheme, MeetingSheme
from app.src.dal.database.models import EventModel, MeetingModel
from app.src.dal.database.repositories import (
    EventRepository,
    MeetingRepository,
    TeamRepository,
    UserRepository,
)

logger = getLogger(__name__)


class EventService(BaseService):
    """
    Сервис управления событиями.

    Аргументы (все зависимости внедряются через методы):
        None (все зависимости передаются как параметры).

    Методы:
        create_event: создаёт новое событие.
        get_events_for_user: получает события пользователя с пагинацией.
        update_event: обновляет событие.
        delete_event: удаляет событие.
    """

    async def create_event(
        self,
        event_repo: EventRepository,
        user_repo: UserRepository,
        user_id: UUID,
        name: str,
        description: str | None,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> EventSheme:
        """
        Создаёт новое событие.

        Аргументы:
            event_repo: EventRepository
            user_repo: UserRepository
            user_id: UUID — ID пользователя
            name: str
            description: str | None
            start_datetime: datetime
            end_datetime: datetime

        Возвращает:
            EventSheme — созданное событие

        Исключения:
            UserNotFound: если пользователь не найден
        """
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise EventNotFound()
        
        if end_datetime <= start_datetime:
            raise ValueError(
                f"end_datetime ({end_datetime}) должен быть строго после "
                f"start_datetime ({start_datetime})"
            )

        event = EventModel(
            name=name,
            description=description,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )
        await event_repo.create(event)

        return EventSheme.model_validate(event)

    async def get_events_for_user(
        self,
        event_repo: EventRepository,
        user_id: UUID,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[EventSheme], int]:
        """
        Получает события пользователя с пагинацией.

        Аргументы:
            event_repo: EventRepository
            user_id: UUID
            page: int
            page_size: int

        Возвращает:
            (list[EventSheme], int) — список событий и общее количество
        """
        events, total = await event_repo.get_all_paginated(page, page_size)
        return [EventSheme.model_validate(e) for e in events], total

    async def update_event(
        self,
        event_repo: EventRepository,
        event_id: UUID,
        name: str | None = None,
        description: str | None = None,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> EventSheme:
        """
        Обновляет событие.

        Аргументы:
            event_repo: EventRepository
            event_id: UUID
            name: str | None
            description: str | None
            start_datetime: datetime | None
            end_datetime: datetime | None

        Возвращает:
            EventSheme — обновлённое событие

        Исключения:
            EventNotFound
        """
        event = await event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFound()

        if name is not None:
            event.name = name
        if description is not None:
            event.description = description
        if start_datetime is not None:
            event.start_datetime = start_datetime
        if end_datetime is not None:
            event.end_datetime = end_datetime
        
        # Валидация временных интервалов: используем новые значения, если они переданы, иначе старые
        current_start = start_datetime if start_datetime is not None else event.start_datetime
        current_end = end_datetime if end_datetime is not None else event.end_datetime

        if current_end <= current_start:
            raise ValueError(
                f"end_datetime ({current_end}) должен быть строго после "
                f"start_datetime ({current_start})"
            )
        
        event.updated_at = datetime.now(timezone.utc)

        await event_repo.update(event)
        return EventSheme.model_validate(event)

    async def delete_event(
        self,
        event_repo: EventRepository,
        event_id: UUID,
    ) -> None:
        """
        Удаляет событие.

        Аргументы:
            event_repo: EventRepository
            event_id: UUID

        Исключения:
            EventNotFound
        """
        event = await event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFound()
        await event_repo.delete(event)
        
        
        


class MeetingService(BaseService):
    """
    Сервис управления встречами.

    Аргументы (все зависимости внедряются через методы):
        None (все зависимости передаются как параметры).

    Методы:
        create_meeting: создаёт новую встречу.
        get_meetings_for_team: получает встречи команды с пагинацией.
        update_meeting: обновляет встречу.
        delete_meeting: удаляет встречу.
    """

    async def create_meeting(
        self,
        meeting_repo: MeetingRepository,
        team_repo: TeamRepository,
        team_id: UUID,
        name: str,
        description: str | None,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> MeetingSheme:
        """
        Создаёт новую встречу.

        Аргументы:
            meeting_repo: MeetingRepository
            team_repo: TeamRepository
            team_id: UUID — ID команды
            name: str
            description: str | None
            start_datetime: datetime
            end_datetime: datetime

        Возвращает:
            MeetingSheme — созданная встреча

        Исключения:
            TeamNotFound: если команда не найдена
        """
        team = await team_repo.get_by_id(team_id)
        if not team:
            raise MeetingNotFound()

        meeting = MeetingModel(
            name=name,
            description=description,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )
        await meeting_repo.create(meeting)

        return MeetingSheme.model_validate(meeting)

    async def get_meetings_for_team(
        self,
        meeting_repo: MeetingRepository,
        team_id: UUID,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[MeetingSheme], int]:
        """
        Получает встречи команды с пагинацией.

        Аргументы:
            meeting_repo: MeetingRepository
            team_id: UUID
            page: int
            page_size: int

        Возвращает:
            (list[MeetingSheme], int) — список встреч и общее количество
        """
        meetings, total = await meeting_repo.get_all_paginated(page, page_size)
        return [MeetingSheme.model_validate(m) for m in meetings], total

    async def update_meeting(
        self,
        meeting_repo: MeetingRepository,
        meeting_id: UUID,
        name: str | None = None,
        description: str | None = None,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> MeetingSheme:
        """
        Обновляет встречу.

        Аргументы:
            meeting_repo: MeetingRepository
            meeting_id: UUID
            name: str | None
            description: str | None
            start_datetime: datetime | None
            end_datetime: datetime | None

        Возвращает:
            MeetingSheme — обновлённая встреча

        Исключения:
            MeetingNotFound
        """
        meeting = await meeting_repo.get_by_id(meeting_id)
        if not meeting:
            raise MeetingNotFound()

        if name is not None:
            meeting.name = name
        if description is not None:
            meeting.description = description
        if start_datetime is not None:
            meeting.start_datetime = start_datetime
        if end_datetime is not None:
            meeting.end_datetime = end_datetime
        meeting.updated_at = datetime.now(timezone.utc)

        await meeting_repo.update(meeting)
        return MeetingSheme.model_validate(meeting)

    async def delete_meeting(
        self,
        meeting_repo: MeetingRepository,
        meeting_id: UUID,
    ) -> None:
        """
        Удаляет встречу.

        Аргументы:
            meeting_repo: MeetingRepository
            meeting_id: UUID

        Исключения:
            MeetingNotFound
        """
        meeting = await meeting_repo.get_by_id(meeting_id)
        if not meeting:
            raise MeetingNotFound()
        await meeting_repo.delete(meeting)