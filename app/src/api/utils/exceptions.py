from fastapi import HTTPException
from http import HTTPStatus


class AppException(HTTPException):
    """Базовое исключение для всех бизнес-ошибок."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class UserAlreadyExists(AppException):
    """Пользователь с указанным email уже существует."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.CONFLICT, detail="Пользователь с таким email уже существует.")


class UserNotFound(AppException):
    """Пользователь не найден."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.NOT_FOUND, detail="Пользователь не найден.")


class InvalidCredentials(AppException):
    """Неверные учетные данные (email/пароль)."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.UNAUTHORIZED, detail="Неверный email или пароль.")


class TeamNotFound(AppException):
    """Команда не найдена."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.NOT_FOUND, detail="Команда не найдена.")


class TeamAlreadyExists(AppException):
    """Команда с таким названием уже существует."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.CONFLICT, detail="Команда с таким названием уже существует.")


class TaskNotFound(AppException):
    """Задача не найдена."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.NOT_FOUND, detail="Задача не найдена.")


class AccessDenied(AppException):
    """Нет прав для выполнения операции."""
    def __init__(self, detail: str = "Недостаточно прав для выполнения операции."):
        super().__init__(status_code=HTTPStatus.FORBIDDEN, detail=detail)
        
class MeetingNotFound(AppException):
    """Встреча не найдена."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.NOT_FOUND, detail="Встреча не найдена.")
        
class EventNotFound(AppException):
    """Событие не найдена."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.NOT_FOUND, detail="Событие не найдена.")

class ProjectNotFound(AppException):
    """Проект не найден."""
    def __init__(self):
        super().__init__(status_code=HTTPStatus.NOT_FOUND, detail="Проект не найдена.")

        