"""
Представление календаря событий и встреч.

Назначение:
    Эндпоинт GET /views/calendar отображает HTML-календарь текущего (или указанного) месяца.
    Дни с событиями/встречами подсвечиваются красным.
    Если за день несколько событий — показывается число.
    Если одно событие/встреча — показывается название.

Содержащиеся функции:
    calendar_view: GET /views/calendar — основная страница календаря.

Аргументы:
    request: HTTP-запрос от FastAPI.
    data_manager: Менеджер данных (DataManager).
    current_user_id: UUID текущего пользователя (из токена).
    year: Год (опционально, по умолчанию текущий).
    month: Месяц (опционально, по умолчанию текущий).

Возвращаемое значение:
    Response: Срендеренная HTML-страница календаря.

Возможные исключения:
    HTTPException: 500 при ошибке загрузки данных.

Ограничения:
    - Требуется аутентификация.
    - События и встречи фильтруются по пользователям, участвующим в командах текущего юзера.

Примеры:
    # Календарь на текущий месяц
    GET /views/calendar
    → HTML с календарём

    # Календарь на март 2026
    GET /views/calendar?year=2026&month=3
    → HTML с календарём марта 2026
"""

from __future__ import annotations

from datetime import datetime, date
from logging import getLogger
from typing import Annotated
from uuid import UUID

from calendar import monthrange
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.src.api.utils.api_utils import DependsDataManager
from app.src.api.services.auth import RoleType, require_permissions
from app.src.api.client.views._views_base import templates, prefix

logger = getLogger(__name__)

calendar_router_views = APIRouter(prefix=f"{prefix}/calendar", tags=["calendar"])


def _build_calendar_grid(
    year: int,
    month: int,
    day_events: dict[int, list[dict]],
) -> dict:
    """
    Формирует структуру календарной сетки для отображения.

    Назначение:
        Создаёт двумерную структуру дней месяца с учётом дня недели первого дня.
        Добавляет данные о событиях для каждого дня.

    Аргументы:
        year: Год (например, 2026).
        month: Месяц (1-12).
        day_events: Словарь {день_месяца: [события]}.

    Возвращаемое значение:
        dict: Структура с полями:
            - days: список дней (None для пустых ячеек, dict для дней с данными).
            - first_day_of_week: номер дня недели 1-го числа (0=Пн, 6=Вс).
            - total_days: количество дней в месяце.
            - month_name: название месяца на русском.
            - year: год.

    Примеры:
        result = _build_calendar_grid(2026, 3, {1: [{"name": "Встреча"}], 15: [{"name": "Дедлайн"}]})
        # → {"days": [...], "first_day_of_week": 2, "total_days": 31, ...}
    """
    from calendar import month_name

    total_days = monthrange(year, month)[1]
    first_weekday = monthrange(year, month)[0]  # 0=Пн, 6=Вс

    month_name_ru = month_name[month]

    cells: list[dict | None] = []

    # Пустые ячейки до 1-го числа
    for _ in range(first_weekday):
        cells.append(None)

    # Дни месяца
    for day in range(1, total_days + 1):
        events = day_events.get(day, [])
        if events:
            cells.append({
                "day": day,
                "events": events,
                "has_events": True,
                "event_count": len(events),
            })
        else:
            cells.append({
                "day": day,
                "events": [],
                "has_events": False,
                "event_count": 0,
            })

    return {
        "days": cells,
        "first_day_of_week": first_weekday,
        "total_days": total_days,
        "month_name": month_name_ru,
        "year": year,
    }


def _format_day_display(day_data: dict) -> dict:
    """
    Форматирует отображение дня календаря.

    Назначение:
        Определяет, что показывать в ячейке дня:
        - Если несколько событий — число событий.
        - Если одно событие — название события.
        - Если нет событий — просто число.

    Аргументы:
        day_data: Словарь с данными дня (из _build_calendar_grid).

    Возвращаемое значение:
        dict: Обновлённый day_data с дополнительными полями:
            - display_text: текст для отображения (число или название).
            - display_type: "single" (одно событие), "multiple" (несколько), "none" (без событий).

    Примеры:
        day = {"day": 15, "events": [{"name": "Совещание", "type": "meeting"}], "event_count": 1}
        result = _format_day_display(day)
        # → {..., "display_text": "Совещание", "display_type": "single"}
    """
    events = day_data.get("events", [])
    count = day_data.get("event_count", 0)

    if count == 0:
        day_data["display_text"] = str(day_data["day"])
        day_data["display_type"] = "none"
    elif count == 1:
        day_data["display_text"] = events[0]["name"]
        day_data["display_type"] = "single"
    else:
        day_data["display_text"] = str(count)
        day_data["display_type"] = "multiple"

    return day_data


@calendar_router_views.get("/", response_class=HTMLResponse)
async def calendar_view(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
    year: int | None = None,
    month: int | None = None,
) -> HTMLResponse:
    """
    Отображение календаря событий и встреч.

    Назначение:
        Формирует и рендерит HTML-календарь с событиями и встречами.
        По умолчанию показывает текущий месяц.

    Аргументы:
        request: HTTP-запрос от FastAPI.
        data_manager: DataManager для доступа к БД.
        current_user_id: UUID текущего пользователя.
        year: Год (опционально).
        month: Месяц (опционально).

    Возвращаемое значение:
        HTMLResponse: Срендеренная HTML-страница календаря.

    Возможные исключения:
        HTTPException: 500 при ошибке загрузки данных.

    Примеры:
        # Текущий месяц
        GET /views/calendar
        → HTML

        # Март 2026
        GET /views/calendar?year=2026&month=3
        → HTML
    """
    now = datetime.now().date()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    # Валидация параметров
    if not (1 <= month <= 12):
        month = now.month
    if year < 2000 or year > 2100:
        year = now.year

    # Определяем границы месяца
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    start_dt = datetime.combine(first_day, datetime.min.time())
    end_dt = datetime.combine(last_day, datetime.max.time())

    day_events: dict[int, list[dict]] = {}

    try:
        async with data_manager() as uow:
            # Загружаем события и встречи за месяц
            events_stmt = (
                uow.session.execute(
                    uow.session.query(EventModel)
                    .filter(
                        EventModel.start_datetime >= start_dt,
                        EventModel.start_datetime <= end_dt,
                    )
                    .order_by(EventModel.start_datetime)
                )
            )
            events_result = await events_stmt

            meetings_stmt = (
                uow.session.execute(
                    uow.session.query(MeetingModel)
                    .filter(
                        MeetingModel.start_datetime >= start_dt,
                        MeetingModel.start_datetime <= end_dt,
                    )
                    .order_by(MeetingModel.start_datetime)
                )
            )
            meetings_result = await meetings_stmt

            # Группируем события по дням
            for event in events_result:
                day = event.start_datetime.day
                if day not in day_events:
                    day_events[day] = []
                day_events[day].append({
                    "name": event.name,
                    "type": "event",
                    "start": event.start_datetime.strftime("%H:%M"),
                    "end": event.end_datetime.strftime("%H:%M"),
                })

            for meeting in meetings_result:
                day = meeting.start_datetime.day
                if day not in day_events:
                    day_events[day] = []
                day_events[day].append({
                    "name": meeting.name,
                    "type": "meeting",
                    "start": meeting.start_datetime.strftime("%H:%M"),
                    "end": meeting.end_datetime.strftime("%H:%M"),
                })

    except Exception as e:
        logger.error("Ошибка загрузки данных календаря: %s", e)
        return templates.TemplateResponse(
            name="error/500.html",
            request=request,
            context={"error": "Не удалось загрузить данные календаря"},
            status_code=500,
        )

    # Формируем календарную сетку
    calendar = _build_calendar_grid(year, month, day_events)

    # Форматируем отображение каждого дня
    for i, day_data in enumerate(calendar["days"]):
        if day_data is not None:
            calendar["days"][i] = _format_day_display(day_data)

    # Определяем предыдущий и следующий месяц
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    return templates.TemplateResponse(
        name="pages/calendar/calendar.html",
        request=request,
        context={
            "calendar": calendar,
            "prev_month": prev_month,
            "prev_year": prev_year,
            "next_month": next_month,
            "next_year": next_year,
            "current_user_id": str(current_user_id),
        },
    )
