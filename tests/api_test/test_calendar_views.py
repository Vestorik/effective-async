"""
Модуль тестирования представлений календаря (calendar_views).

Покрытие:
    1. Unit-тесты для вспомогательных функций:
       - _build_calendar_grid: проверка логики формирования сетки месяца.
       - _format_day_display: проверка логики отображения событий в ячейке.
    2. Integration-тесты для эндпоинта GET /views/calendar/:
       - Happy path: успешная отрисовка календаря с данными.
       - Edge case: переход через месяц (декабрь/январь).
       - Failure case: эмуляция ошибки базы данных.

Зависимости:
    pytest, pytest-asyncio, fastapi.testclient.TestClient
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# Импортируем тестируемые функции и роутер
from app.src.api.client.views.calendar.calendar_views import (
    _build_calendar_grid,
    _format_day_display,
    calendar_router_views,
)

# --- Unit Tests ---


class TestBuildCalendarGrid:
    """Тесты для функции _build_calendar_grid."""

    def test_build_grid_standard_month(self):
        """
        Проверка формирования сетки для обычного месяца (например, Март 2026).
        Март 2026 начинается с субботы (first_weekday = 5, если 0=Пн).
        """
        year = 2026
        month = 3
        day_events = {1: [{"name": "New Event"}], 15: [{"name": "Meeting"}]}

        result = _build_calendar_grid(year, month, day_events)

        # Март 2026 имеет 31 день
        assert result["total_days"] == 31
        assert result["year"] == year
        assert result["month_name"] == "март"
        
        # Проверка количества ячеек: пропуски + дни
        # 1 марта 2026 - суббота. В Python calendar.monthrange: 0=Пн, ..., 5=Сб.
        # Значит first_day_of_week должно быть 5.
        assert result["first_day_of_week"] == 5
        
        # Всего ячеек: 5 (пустых) + 31 (дней) = 36
        assert len(result["days"]) == 36
        
        # Проверка первого пустого элемента
        assert result["days"][0] is None
        
        # Проверка первого дня (индекс 5)
        day_cell = result["days"][5]
        assert day_cell["day"] == 1
        assert day_cell["has_events"] is True
        assert day_cell["event_count"] == 1
        assert day_cell["events"][0]["name"] == "New Event"

    def test_build_grid_empty_month(self):
        """Проверка месяца без событий."""
        result = _build_calendar_grid(2026, 1, {}) # Январь 2026
        
        assert result["total_days"] == 31
        assert all(day is not None for day in result["days"][-31:])
        # Все дни должны быть с пустыми событиями
        for day_cell in result["days"]:
            if day_cell:
                assert day_cell["has_events"] is False
                assert day_cell["event_count"] == 0


class TestFormatDayDisplay:
    """Тесты для функции _format_day_display."""

    def test_format_no_events(self):
        """День без событий должен показывать только число."""
        day_data = {
            "day": 15,
            "events": [],
            "event_count": 0,
        }
        result = _format_day_display(day_data)
        
        assert result["display_text"] == "15"
        assert result["display_type"] == "none"

    def test_format_single_event(self):
        """Одно событие должно показывать его название."""
        day_data = {
            "day": 15,
            "events": [{"name": "Совещание", "type": "meeting"}],
            "event_count": 1,
        }
        result = _format_day_display(day_data)
        
        assert result["display_text"] == "Совещание"
        assert result["display_type"] == "single"

    def test_format_multiple_events(self):
        """Несколько событий должны показывать количество."""
        day_data = {
            "day": 15,
            "events": [
                {"name": "Встреча 1"},
                {"name": "Встреча 2"}
            ],
            "event_count": 2,
        }
        result = _format_day_display(day_data)
        
        assert result["display_text"] == "2"
        assert result["display_type"] == "multiple"

    def test_format_invalid_count(self):
        """Если event_count=0, но events не пустой (защита от несогласованности данных)."""
        # По логике _build_calendar_grid, если events есть, count > 0.
        # Но тест должен обрабатывать входные данные корректно.
        day_data = {
            "day": 15,
            "events": [{"name": "Event"}],
            "event_count": 0, # Несогласованное состояние
        }
        # Функция смотрит на count сначала.
        result = _format_day_display(day_data)
        assert result["display_text"] == "15"
        assert result["display_type"] == "none"


# --- Integration Tests ---

# Создаем минимальное приложение для теста, чтобы внедрить роутер
app = FastAPI()
app.include_router(calendar_router_views)


class TestCalendarViewEndpoint:
    """
    Integration-тесты для эндпоинта calendar_view.
    
    Для изоляции тестов мы переопределяем зависимости FastAPI:
    1. DependsDataManager: возвращаем мок UOW с контроллируемыми данными.
    2. RequirePermissions: возвращаем фиксированный user_id.
    3. templates: в реальном коде он глобален, но в тестах мы можем не трогать его,
       если Mock клиент не рендерит шаблон, либо подменять templates, если нужно.
       Однако TestClient обычно не рендерит шаблон полностью, если просто проверить статус.
       Но нам нужен контекст для проверки ссылок на предыдущий/следующий месяц.
       Поэтому мы проверим возвращаемый контекст через анализ ответа или мока templates.
    """

    @pytest.fixture
    def client(self):
        """Фикстура TestClient с переопределёнными зависимостями."""
        with TestClient(app) as client:
            yield client

    def _mock_data_manager(self, events_data, meetings_data):
        """
        Создает мок для DependsDataManager.
        Возвращает контекстный менеджер, который симулирует работу БД.
        """
        mock_uow = MagicMock()
        
        # Мок сессии и query
        mock_session = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow.__aexit__.return_value = None
        mock_uow.session = mock_session

        # Создаем фейковые объекты моделей для SQLAlchemy query
        class FakeQuery:
            def __init__(self, data):
                self.data = data
                
            def filter(self, *args, **kwargs):
                return self
                
            def order_by(self, *args):
                return self

        class FakeExecuteResult:
            def __init__(self, data):
                self.data = data
                self._idx = 0
                
            def __aiter__(self):
                return self
            
            def __anext__(self):
                if self._idx >= len(self.data):
                    raise StopAsyncIteration
                item = self.data[self._idx]
                self._idx += 1
                return item

        # Настройка mock.execute для разных моделей
        execute_calls = []
        
        def mock_execute(query_obj):
            # Определяем, какой тип объекта передан (MeetingModel или EventModel) по первому аргументу query()
            # В реальном коде query(obj) -> execute(stmt)
            # Упрощенная логика: мы подменяем execute так, чтобы он возвращал нужные данные
            # Поскольку у нас hardcode запросы, хитро. 
            # Проще: перепишем зависимость так, чтобы она вызывала наши данные.
            pass

        # Более надежный способ: переопределить сам метод получения данных внутри test,
        # или использовать patch.
        # Так как _calendar_view использует hardcode UOW, смоделируем его поведение.
        
        # Создаем асинхронный контекстный менеджер для mock_uow
        async def enter():
            # Создаем "результаты" запросов
            # Формат: список словарей, соответствующих атрибутам моделей
            # EventModel: name, start_datetime, end_datetime
            # MeetingModel: name, start_datetime, end_datetime
            
            class FakeRow:
                def __init__(self, data):
                    self.name = data["name"]
                    self.start_datetime = data["start"]
                    self.end_datetime = data["end"]
            
            fake_events = [FakeRow(e) for e in events_data]
            fake_meetings = [FakeRow(m) for m in meetings_data]
            
            # Мок сессии
            mock_session_obj = MagicMock()
            mock_uow.session = mock_session_obj
            
            # Мок execute
            def execute(query):
                # Это сложно из-за chain calls. 
                # Проще всего захватить контекст UOW в тесте и подменить его.
                pass

            mock_uow.session.execute = MagicMock()
            
            # Настроим execute так, чтобы он возвращал Correct AsyncIter
            def side_effect(query):
                # Определяем тип по первому элементу query.entities или подобному,
                # но в asyncpg/alchemy это сложно определить без introspection.
                # Вместо этого, в реальном юните-тесте для endpoint, 
                # лучше всего использовать `patch` на уровне модуля.
                return AsyncIter(fake_events) # Это заглушка, см. ниже

            return mock_uow

        # Для простоты в интеграционных тестах FastAPI, 
        # мы будем патчить функцию внутри views, если это возможно,
        # или передавать мок data_manager через dependency override.
        
        return None # Будем использовать прямое патчинг в тесте

    @patch("app.src.api.client.views.calendar.calendar_views.data_manager")
    @patch("app.src.api.client.views.calendar.calendar_views.RequirePermissions")
    def test_calendar_view_happy_path(self, mock_req_perms, mock_dm):
        """
        Happy path: Запрос календаря на текущий месяц с событиями.
        Проверяем, что статус 200 и шаблон вызван.
        """
        mock_req_perms.return_value = lambda: uuid4()
        
        # Подготавливаем мок UOW
        mock_uow_instance = MagicMock()
        
        # Мокаем async context manager
        async def mock_aenter():
            return mock_uow_instance
        
        async def mock_aexit(*args):
            pass
            
        mock_uow_instance.__aenter__ = mock_aenter
        mock_uow_instance.__aexit__ = mock_aexit
        
        # Подготавливаем фейковые данные из БД
        base_dt = date(2026, 3, 1)
        event_data = {
            "name": "Test Event",
            "start": datetime.combine(base_dt, datetime.min.time()),
            "end": datetime.combine(base_dt, datetime.max.time()),
        }
        meeting_data = {
            "name": "Test Meeting",
            "start": datetime.combine(base_dt, datetime.min.time()),
            "end": datetime.combine(base_dt, datetime.max.time()),
        }

        # Мокаем execute для двух вызовов (query Event, query Meeting)
        call_args = []
        
        def side_effect_query(query_model):
            call_args.append(query_model)
            # Возвращаем результат, который ведет себя как Query
            class MockStmt:
                def __await__(self):
                    # Если это EventModel
                    if "EventModel" in str(query_model) or call_args.count(query_model) == 1:
                        result = [event_data] # Упрощение: список результатов одного хода? 
                                              # Нет, execute возвращает Statement, потом await дает Rows.
                    yield [event_data] # Это неверный паттерн async генератора для.await

            return MockStmt()

        # Более простой подход для интеграции:
        # Мы не можем легко перехватить `uow.session.query().execute()` без глубокого патчинга.
        # Поэтому изменим тест на проверку того, что шаблон рендерится корректно 
        # с передачей контекста.
        
        # Перепишем тестовый сценарий:
        # Мы используем TestClient, но переопределяем саму зависимость `data_manager` 
        # так, чтобы она возвращала объект, который при вызове async with дает мок сессии.
        
        # Создаем моки для SQLAlchemy объектов
        mock_session = MagicMock()
        mock_uow_instance.session = mock_session
        
        # Создаем фейковые "строки" результатов
        class FakeRow:
            def __init__(self, name, start, end):
                self.name = name
                self.start_datetime = start
                self.end_datetime = end
                
        # Данные
        now = datetime.now().date()
        year = now.year
        month = now.month
        
        # Формируем тестовые события для текущего месяца
        test_events = [
            FakeRow("Event 1", datetime.now().replace(day=15), datetime.now().replace(day=15, hour=23))
        ]
        test_meetings = [
            FakeRow("Meeting 1", datetime.now().replace(day=20), datetime.now().replace(day=20, hour=12))
        ]
        
        # Мокаем execute, чтобы он возвращал асинхронный итератор с этими данными
        # SQLAlchemy Core execute(stmt) -> Statement. 
        # В FastAPI+SQLAlchemy обычно используют `result = await session.execute(...)`.
        
        async def execute_mock(query):
            # Определяем тип запроса
            # query - это Query object. Он не сериализуем просто так.
            # Но мы можем проверить, есть ли в нем EventModel.
            # В реальном коде это сложно.
            # Проще: предположим, что мы перехватили вызовы.
            
            # Для теста вернем заглушку, которая "сработает"
            return FakeAsyncIterator([test_events[0] if "Event" in str(query) else test_meetings[0]])

        class FakeAsyncIterator:
            def __init__(self, data):
                self.data = data
                self.idx = 0
                
            def __aiter__(self):
                return self
                
            def __anext__(self):
                if self.idx >= len(self.data):
                    raise StopAsyncIteration
                val = self.data[self.idx]
                self.idx += 1
                return val

        mock_session.execute = execute_mock
        
        # Теперь мокаем саму функцию data_manager
        mock_dm.return_value = MagicMock()
        mock_dm.return_value.__aenter__ = lambda self: mock_uow_instance
        mock_dm.return_value.__aexit__ = lambda self, *args: None

        # Вызов эндпоинта
        response = app.test_client().get("/views/calendar")
        
        # Проверяем статус
        assert response.status_code == 200
        
        # Проверяем, что был вызван шаблон (TestClient возвращает HTML)
        assert "html" in response.headers.get("content-type", "")
        
        # Так как мы не рендерим шаблон полностью (у нас нет Jinja2 шаблонов в тесте),
        # мы можем проверить, что контекст передан правильно, запатчав TemplateResponse
       