from pydantic import ValidationError
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.exceptions import HTTPException

from app.src.api.handlers.event_handlers import (
    create_event,
    get_event_by_id,
    update_event,
    delete_event,
)
from app.src.api.shems import EventCreate, MeetingCreate
from app.src.api.exceptions import EventNotFound, MeetingNotFound
import app.src.api.handlers.event_handlers as mod


class TestEventHandlers:
    @pytest.fixture
    def mocks(self):
        """Общие моки, чтобы не дублировать в каждом тесте."""
        data_manager = MagicMock()
        uow = MagicMock()
        data_manager.return_value.__aenter__.return_value = uow
        uow.events = MagicMock()
        uow.users = MagicMock()

        # Мок для кэшированного UOW (нужен для get_event_by_id)
        cuow = MagicMock()
        data_manager.cache.return_value.__aenter__.return_value = cuow

        return {
            "data_manager": data_manager,
            "uow": uow,
            "cuow": cuow,
        }

    @pytest.fixture
    def patch_service(self):
        """Фикстура для подмены EventService в модуле."""
        old_EventService = mod.EventService
        mock_service = AsyncMock()

        def teardown():
            mod.EventService = old_EventService

        yield mock_service
        teardown()

    @pytest.mark.asyncio
    async def test_create_event_happy(self, mocks, patch_service):
        user_id = uuid.uuid4()
        payload = EventCreate(
            name="test",
            description="desc",
            start_datetime="2025-12-10T10:00:00Z",
            end_datetime="2025-12-10T11:00:00Z",
        )

        patch_service.create_event.return_value = {"id": str(uuid.uuid4()), "name": "test"}
        mod.EventService = lambda: patch_service  # ty: ignore[invalid-assignment]

        res = await create_event(
            event_data=payload,
            user_id=user_id,
            data_manager=mocks["data_manager"],
        )
        assert res is not None


    @pytest.mark.asyncio
    async def test_get_event_by_id_not_found(self, mocks):
        eid = uuid.uuid4()
        mocks["cuow"].events.get_by_id = AsyncMock(return_value=None)

        from app.src.api.handlers.event_handlers import get_event_by_id
        with pytest.raises(HTTPException) as e:
            await get_event_by_id(event_id=eid, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_event_found(self, mocks, patch_service):
        eid = uuid.uuid4()
        payload = EventCreate(
            name="updated",
            description="new",
            start_datetime="2025-12-10T10:00:00Z",
            end_datetime="2025-12-10T11:00:00Z",
        )

        patch_service.update_event.return_value = {"id": str(eid), "name": "updated"}
        mod.EventService = lambda: patch_service  # ty: ignore[invalid-assignment]

        res = await update_event(
            event_id=eid,
            event_update=payload,
            data_manager=mocks["data_manager"],
        )
        assert res is not None

    @pytest.mark.asyncio
    async def test_update_event_not_found(self, mocks, patch_service):
        eid = uuid.uuid4()
        payload = EventCreate(
            name="upd",
            description="new",
            start_datetime="2025-12-10T10:00:00Z",
            end_datetime="2025-12-10T11:00:00Z",
        )

        patch_service.update_event.side_effect = EventNotFound()
        mod.EventService = lambda: patch_service  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await update_event(
                event_id=eid,
                event_update=payload,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_event_success(self, mocks, patch_service):
        eid = uuid.uuid4()
        patch_service.delete_event.return_value = None
        mod.EventService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        res = await delete_event(event_id=eid, data_manager=mocks["data_manager"])
        # delete_event возвращает None, FastAPI сам сделает 204
        assert res is None

    @pytest.mark.asyncio
    async def test_delete_event_not_found(self, mocks, patch_service):
        eid = uuid.uuid4()
        patch_service.delete_event.side_effect = EventNotFound()
        mod.EventService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await delete_event(event_id=eid, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404



class TestMeetingHandlers:
    @pytest.fixture
    def mocks(self):
        """Моки для обработчиков встреч."""
        data_manager = MagicMock()
        uow = MagicMock()
        data_manager.return_value.__aenter__.return_value = uow
        uow.meetings = MagicMock()
        uow.teams = MagicMock()

        cuow = MagicMock()
        data_manager.cache.return_value.__aenter__.return_value = cuow

        return {
            "data_manager": data_manager,
            "uow": uow,
            "cuow": cuow,
        }

    @pytest.fixture
    def patch_meeting_service(self):
        """Фикстура для подмены MeetingService в модуле."""
        old_MeetingService = mod.MeetingService
        mock_service = AsyncMock()

        def teardown():
            mod.MeetingService = old_MeetingService

        yield mock_service
        teardown()

    @pytest.fixture
    def patch_event_service(self):
        """Фикстура для подмены EventService (используется для get_meetings_for_team, если логика там, 
        но в коде handlers.py используется MeetingService для get_meetings_for_team).
        Убедимся, что используем правильный сервис.
        """
        pass # Не используется, используем patch_meeting_service

    @pytest.mark.asyncio
    async def test_create_meeting_success(self, mocks, patch_meeting_service):
        """
        Scenario: Успешное создание встречи.
        """
        team_id = uuid.uuid4()
        payload = MeetingCreate(
            name="Meeting",
            description="Desc",
            start_datetime="2025-12-10T10:00:00Z",
            end_datetime="2025-12-10T11:00:00Z",
        )
        
        mock_meeting = MagicMock(id=uuid.uuid4(), name="Meeting")
        patch_meeting_service.create_meeting.return_value = mock_meeting
        mod.MeetingService = lambda: patch_meeting_service

        from app.src.api.handlers.event_handlers import create_meeting
        res = await create_meeting(
            meeting_data=payload,
            team_id=team_id,
            data_manager=mocks["data_manager"],
        )
        assert res is not None
        patch_meeting_service.create_meeting.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_meeting_invalid_datetime(self, mocks, patch_meeting_service):
        """
        Scenario: Ошибка валидации времени (ValueError).
        """
        team_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            payload = MeetingCreate(
                name="Bad Meeting",
                description="Desc",
                start_datetime="2025-12-10T12:00:00Z", # После end
                end_datetime="2025-12-10T10:00:00Z",
            )
            

    @pytest.mark.asyncio
    async def test_create_meeting_team_not_found(self, mocks, patch_meeting_service):
        """
        Scenario: Команда не найдена.
        """
        team_id = uuid.uuid4()
        payload = MeetingCreate(
            name="Meeting",
            description="Desc",
            start_datetime="2025-12-10T10:00:00Z",
            end_datetime="2025-12-10T11:00:00Z",
        )
        
        patch_meeting_service.create_meeting.side_effect = MeetingNotFound()
        mod.MeetingService = lambda: patch_meeting_service

        from app.src.api.handlers.event_handlers import create_meeting
        with pytest.raises(HTTPException) as e:
            await create_meeting(
                meeting_data=payload,
                team_id=team_id,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_meeting_by_id_success(self, mocks):
        import uuid
        from datetime import datetime, timezone

        mid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_meeting_data = {
            "name": "Test Meeting",
            "start_datetime": now,                 # обязательно
            "end_datetime": now.replace(hour=now.hour + 1),  # обязательно
        }

        mocks["cuow"].meetings.get_by_id = AsyncMock(return_value=mock_meeting_data)

        from app.src.api.handlers.event_handlers import get_meeting_by_id
        res = await get_meeting_by_id(meeting_id=mid, data_manager=mocks["data_manager"])

        assert res is not None
        assert res.name == "Test Meeting"

        
    @pytest.mark.asyncio
    async def test_get_meeting_by_id_not_found(self, mocks):
        """
        Scenario: Встреча не найдена.
        """
        mid = uuid.uuid4()
        mocks["cuow"].meetings.get_by_id = AsyncMock(return_value=None)

        from app.src.api.handlers.event_handlers import get_meeting_by_id
        with pytest.raises(HTTPException) as e:
            await get_meeting_by_id(meeting_id=mid, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_meetings_for_team_success(self, mocks):
        """
        Scenario: Успешное получение списка встреч команды.
        """
        team_id = uuid.uuid4()
        mock_meeting = MagicMock(id=uuid.uuid4(), name="Meeting 1")
        
        patch_meeting_service = MagicMock()
        patch_meeting_service.get_meetings_for_team = AsyncMock(return_value=([mock_meeting], 1))
        mod.MeetingService = lambda: patch_meeting_service

        from app.src.api.handlers.event_handlers import get_meetings_for_team
        res = await get_meetings_for_team(
            team_id=team_id,
            data_manager=mocks["data_manager"],
        )
        assert len(res) == 1

    @pytest.mark.asyncio
    async def test_get_meetings_for_team_not_found(self, mocks):
        """
        Scenario: Команда/встречи не найдены.
        """
        team_id = uuid.uuid4()
        
        patch_meeting_service = MagicMock()
        patch_meeting_service.get_meetings_for_team = AsyncMock(side_effect=MeetingNotFound())
        mod.MeetingService = lambda: patch_meeting_service

        from app.src.api.handlers.event_handlers import get_meetings_for_team
        with pytest.raises(HTTPException) as e:
            await get_meetings_for_team(
                team_id=team_id,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_meeting_success(self, mocks, patch_meeting_service):
        """
        Scenario: Успешное обновление встречи.
        """
        mid = uuid.uuid4()
        payload = MeetingCreate(
            name="Updated Meeting",
            description="New Desc",
            start_datetime="2025-12-10T10:00:00Z",
            end_datetime="2025-12-10T11:00:00Z",
        )
        
        mock_meeting = MagicMock(id=mid, name="Updated Meeting")
        patch_meeting_service.update_meeting.return_value = mock_meeting
        mod.MeetingService = lambda: patch_meeting_service

        from app.src.api.handlers.event_handlers import update_meeting
        res = await update_meeting(
            meeting_id=mid,
            meeting_update=payload,
            data_manager=mocks["data_manager"],
        )
        assert res is not None

