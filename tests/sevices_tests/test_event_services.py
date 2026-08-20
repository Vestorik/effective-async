"""
Тесты для EventService и MeetingService.

Покрытие:
- create_event: успех, пользователь не найден, невалидные даты.
- update_event: частичное обновление (сохранение времени), полное обновление, валидация дат, событие не найдено.
- create_meeting: успех, команда не найдена.
- get_meetings_for_team: пагинация.
- update_meeting: успешное обновление, встреча не найдена.
- delete_meeting: успешное удаление, встреча не найдена.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from app.src.api.services.event_service import EventService, MeetingService
from app.src.api.exceptions import EventNotFound, MeetingNotFound
from app.src.api.shems import EventSheme, MeetingSheme
from app.src.dal.database.models import EventModel, MeetingModel
from app.src.dal.database.repositories import (
    EventRepository,
    MeetingRepository,
    TeamRepository,
    UserRepository,
)


class TestEventServiceCreate:
    """Тесты метода create_event"""

    @pytest.fixture
    def service(self) -> EventService:
        return EventService()

    @pytest.fixture
    def valid_event_data(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "name": "Тестовое событие",
            "description": "Описание",
            "start_datetime": now,
            "end_datetime": now + timedelta(hours=1),
            "user_id": uuid4(),
        }

    @pytest.mark.asyncio
    async def test_create_event_success(self, service: EventService, valid_event_data: dict) -> None:
        """
        Scenario: Успешное создание события.
        """
        # Arrange
        event_repo = AsyncMock(spec=EventRepository)
        user_repo = AsyncMock(spec=UserRepository)
        
        # Мокаем пользователя
        mock_user = AsyncMock()
        mock_user.id = valid_event_data["user_id"]
        user_repo.get_by_id = AsyncMock(return_value=mock_user)
        
        # Мокаем создание события в БД
        event_repo.create = AsyncMock()
        
        # Act
        result = await service.create_event(
            event_repo=event_repo,
            user_repo=user_repo,
            **valid_event_data
        )

        # Assert
        assert isinstance(result, EventSheme)

        event_repo.create.assert_called_once()
        user_repo.get_by_id.assert_called_once_with(valid_event_data["user_id"])

    @pytest.mark.asyncio
    async def test_create_event_user_not_found(self, service: EventService, valid_event_data: dict) -> None:
        """
        Scenario: Пользователь не найден -> EventNotFound.
        """
        # Arrange
        event_repo = AsyncMock(spec=EventRepository)
        user_repo = AsyncMock(spec=UserRepository)
        user_repo.get_by_id = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(EventNotFound):
            await service.create_event(
                event_repo=event_repo,
                user_repo=user_repo,
                **valid_event_data
            )

    @pytest.mark.asyncio
    async def test_create_event_invalid_dates(self, service: EventService, valid_event_data: dict) -> None:
        """
        Scenario: end_datetime <= start_datetime -> ValueError.
        """
        # Arrange
        event_repo = AsyncMock(spec=EventRepository)
        user_repo = AsyncMock(spec=UserRepository)
        user_repo.get_by_id = AsyncMock(return_value=AsyncMock())
        
        # Делаем end_datetime раньше start_datetime
        invalid_data = valid_event_data.copy()
        invalid_data["end_datetime"] = valid_event_data["start_datetime"] - timedelta(hours=1)

        # Act & Assert
        with pytest.raises(ValueError):
            await service.create_event(
                event_repo=event_repo,
                user_repo=user_repo,
                **invalid_data
            )


class TestEventServiceUpdate:
    """Тесты метода update_event"""

    @pytest.fixture
    def service(self) -> EventService:
        return EventService()

    @pytest.fixture
    def existing_event(self) -> EventModel:
        now = datetime.now(timezone.utc)
        # Создаем объект модели корректным способом для SQLAlchemy без sess
        event = EventModel()

        event.name = "Старое имя"
        event.description = "Старое описание"
        event.start_datetime = now
        event.end_datetime = now + timedelta(hours=1)

        return event

    @pytest.mark.asyncio
    async def test_update_event_success(self, service: EventService, existing_event: EventModel) -> None:
        """
        Scenario: Успешное частичное обновление (только имя).
        """
        # Arrange
        event_repo = AsyncMock(spec=EventRepository)
        event_repo.get_by_id = AsyncMock(return_value=existing_event)
        event_repo.update = AsyncMock()

        new_name = "Новое имя"
        
        # Act
        result = await service.update_event(
            event_repo=event_repo,
            event_id=existing_event.id, # id может быть None, но метод expecting UUID, проверим сигнатуру
            name=new_name
        )

        # Assert

        assert result.start_datetime == existing_event.start_datetime
        assert result.end_datetime == existing_event.end_datetime
        event_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_event_partial_update_preserves_unchanged(
        self, service: EventService, existing_event: EventModel
    ) -> None:
        """
        Scenario: Если передаем только name, время должно остаться старым.
        """
        # Arrange
        event_repo = AsyncMock(spec=EventRepository)
        event_repo.get_by_id = AsyncMock(return_value=existing_event)
        event_repo.update = AsyncMock()

        # Act
        await service.update_event(
            event_repo=event_repo,
            event_id=existing_event.id,
            name="Updated Name"
        )

        # Assert: убедимся, что в update отправили объект со старыми датами
        call_args = event_repo.update.call_args[0][0]
        assert call_args.start_datetime == existing_event.start_datetime
        assert call_args.end_datetime == existing_event.end_datetime

    @pytest.mark.asyncio
    async def test_update_event_invalid_new_dates(
        self, service: EventService, existing_event: EventModel
    ) -> None:
        """
        Scenario: Передача некорректных новых дат (конец раньше начала) -> ValueError.
        """
        # Arrange
        event_repo = AsyncMock(spec=EventRepository)
        now = existing_event.start_datetime
        
        event_repo.get_by_id = AsyncMock(return_value=existing_event)
        
        # Передаем некорректные новые даты
        new_start = now + timedelta(days=1)
        new_end = now # Конец раньше начала

        # Act & Assert
        with pytest.raises(ValueError):
            await service.update_event(
                event_repo=event_repo,
                event_id=existing_event.id,
                start_datetime=new_start,
                end_datetime=new_end
            )

    @pytest.mark.asyncio
    async def test_update_event_not_found(self, service: EventService) -> None:
        """
        Scenario: Событие не найдено -> EventNotFound.
        """
        # Arrange
        event_repo = AsyncMock(spec=EventRepository)
        event_repo.get_by_id = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(EventNotFound):
            await service.update_event(
                event_repo=event_repo,
                event_id=uuid4()
            )


class TestMeetingServiceCreate:
    """Тесты метода create_meeting"""

    @pytest.fixture
    def service(self) -> MeetingService:
        return MeetingService()

    @pytest.fixture
    def valid_meeting_data(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "name": "Тестовая встреча",
            "description": "Описание встречи",
            "start_datetime": now,
            "end_datetime": now + timedelta(hours=1),
            "team_id": uuid4(),
        }

    @pytest.mark.asyncio
    async def test_create_meeting_success(self, service: MeetingService, valid_meeting_data: dict) -> None:
        """
        Scenario: Успешное создание встречи.
        """
        # Arrange
        meeting_repo = AsyncMock(spec=MeetingRepository)
        team_repo = AsyncMock(spec=TeamRepository)
        
        # Мокаем команду
        mock_team = AsyncMock()
        mock_team.id = valid_meeting_data["team_id"]
        team_repo.get_by_id = AsyncMock(return_value=mock_team)
        
        meeting_repo.create = AsyncMock()
        
        # Act
        result = await service.create_meeting(
            meeting_repo=meeting_repo,
            team_repo=team_repo,
            **valid_meeting_data
        )

        # Assert

        meeting_repo.create.assert_called_once()
        team_repo.get_by_id.assert_called_once_with(valid_meeting_data["team_id"])

    @pytest.mark.asyncio
    async def test_create_meeting_team_not_found(self, service: MeetingService, valid_meeting_data: dict) -> None:
        """
        Scenario: Команда не найдена -> MeetingNotFound.
        """
        # Arrange
        meeting_repo = AsyncMock(spec=MeetingRepository)
        team_repo = AsyncMock(spec=TeamRepository)
        team_repo.get_by_id = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(MeetingNotFound):
            await service.create_meeting(
                meeting_repo=meeting_repo,
                team_repo=team_repo,
                **valid_meeting_data
            )


class TestMeetingServiceGet:
    """Тесты метода get_meetings_for_team"""

    @pytest.fixture
    def service(self) -> MeetingService:
        return MeetingService()

    @pytest.mark.asyncio
    async def test_get_meetings_success(self, service: MeetingService) -> None:
        """
        Scenario: Успешное получение списка встреч.
        """
        # Arrange
        meeting_repo = AsyncMock(spec=MeetingRepository)
        team_id = uuid4()
        
        # Создаем моки моделей корректно
        m1 = MeetingModel()
        m1.name = "Meeting 1"
        m1.description = ""
        m1.start_datetime = datetime.now(timezone.utc)
        m1.end_datetime = datetime.now(timezone.utc) + timedelta(hours=1)

        m2 = MeetingModel()
        m2.name = "Meeting 2"
        m2.description = ""
        m2.start_datetime = datetime.now(timezone.utc)
        m2.end_datetime = datetime.now(timezone.utc) + timedelta(hours=1)
        
        meeting_repo.get_all_paginated = AsyncMock(return_value=([m1, m2], 2))
        
        # Act
        result_meetings, total = await service.get_meetings_for_team(
            meeting_repo=meeting_repo,
            team_id=team_id,
            page=1,
            page_size=10
        )
        
        # Assert
        assert len(result_meetings) == 2
        assert total == 2


class TestMeetingServiceUpdate:
    """Тесты метода update_meeting"""

    @pytest.fixture
    def service(self) -> MeetingService:
        return MeetingService()

    @pytest.mark.asyncio
    async def test_update_meeting_success(self, service: MeetingService) -> None:
        """
        Scenario: Успешное обновление встречи.
        """
        # Arrange
        meeting_repo = AsyncMock(spec=MeetingRepository)
        meeting_id = uuid4()
        now = datetime.now(timezone.utc)
        
        existing_meeting = MeetingModel()
        existing_meeting.name = "Old Name"
        existing_meeting.description = "Old Desc"
        existing_meeting.start_datetime = now
        existing_meeting.end_datetime = now + timedelta(hours=1)
        
        meeting_repo.get_by_id = AsyncMock(return_value=existing_meeting)
        meeting_repo.update = AsyncMock()

        # Act
        result = await service.update_meeting(
            meeting_repo=meeting_repo,
            meeting_id=meeting_id,
            name="New Name"
        )

        # Assert

        meeting_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_meeting_not_found(self, service: MeetingService) -> None:
        """
        Scenario: Встреча не найдена -> MeetingNotFound.
        """
        # Arrange
        meeting_repo = AsyncMock(spec=MeetingRepository)
        meeting_repo.get_by_id = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(MeetingNotFound):
            await service.update_meeting(
                meeting_repo=meeting_repo,
                meeting_id=uuid4()
            )


class TestMeetingServiceDelete:
    """Тесты метода delete_meeting"""

    @pytest.fixture
    def service(self) -> MeetingService:
        return MeetingService()  # Исправлено: был EventService

    @pytest.mark.asyncio
    async def test_delete_meeting_success(self, service: MeetingService) -> None:
        """
        Scenario: Успешное удаление встречи.
        """
        # Arrange
        meeting_repo = AsyncMock(spec=MeetingRepository)
        meeting_id = uuid4()
        
        # Создаем модель корректно, без передачи team_id в __init__ если это не поддерживается
        existing_meeting = MeetingModel()
        existing_meeting.id = meeting_id
        existing_meeting.name = "Meeting"
        existing_meeting.description = ""
        existing_meeting.start_datetime = datetime.now(timezone.utc)
        existing_meeting.end_datetime = datetime.now(timezone.utc) + timedelta(hours=1)
        
        meeting_repo.get_by_id = AsyncMock(return_value=existing_meeting)
        meeting_repo.delete = AsyncMock()

        # Act
        await service.delete_meeting(
            meeting_repo=meeting_repo,
            meeting_id=meeting_id
        )
        
        # Assert
        meeting_repo.delete.assert_called_once_with(existing_meeting)

    @pytest.mark.asyncio
    async def test_delete_meeting_not_found(self, service: MeetingService) -> None:
        """
        Scenario: Встреча не найдена -> MeetingNotFound.
        """
        # Arrange
        meeting_repo = AsyncMock(spec=MeetingRepository)
        meeting_repo.get_by_id = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(MeetingNotFound):
            await service.delete_meeting(
                meeting_repo=meeting_repo,
                meeting_id=uuid4()
            )