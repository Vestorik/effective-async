from datetime import datetime


def check_time_range(
    start_datetime: datetime,
    end_datetime: datetime,
    min_duration_minutes: int = 1,
) -> None:
    """
    Проверяет валидность временного интервала.

    Аргументы:
        start_datetime (datetime): Время начала интервала.
        end_datetime (datetime): Время окончания интервала.
        min_duration_minutes (int): Минимальная продолжительность в минутах (по умолчанию — 1).

    Исключения:
        ValueError: Если `end_datetime <= start_datetime` или `duration < min_duration_minutes`.

    Примеры:
        >>> check_time_range(
        ...     datetime(2024, 1, 1, 10, 0),
        ...     datetime(2024, 1, 1, 11, 0),
        ... )
        >>> # OK

        >>> check_time_range(
        ...     datetime(2024, 1, 1, 11, 0),
        ...     datetime(2024, 1, 1, 10, 0),
        ... )
        Traceback (most recent call last):
            ...
        ValueError: end_datetime (2024-01-01 11:00:00) должен быть строго после start_datetime (2024-01-01 10:00:00)

        >>> check_time_range(
        ...     datetime(2024, 1, 1, 10, 0),
        ...     datetime(2024, 1, 1, 10, 30),
        ...     min_duration_minutes=60,
        ... )
        Traceback (most recent call last):
            ...
        ValueError: Продолжительность (30 мин) меньше минимальной (60 мин)
    """
    if end_datetime <= start_datetime:
        raise ValueError(
            f"end_datetime ({end_datetime}) должен быть строго после "
            f"start_datetime ({start_datetime})"
        )

    duration_minutes = (end_datetime - start_datetime).total_seconds() / 60
    if duration_minutes < min_duration_minutes:
        raise ValueError(
            f"Продолжительность ({duration_minutes:.0f} мин) меньше "
            f"минимальной ({min_duration_minutes} мин)"
        )