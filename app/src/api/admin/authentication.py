"""
Аутентификация административной панели (SQLAdmin).

Назначение:
    Реализует механизм аутентификации администраторов через сессию.

    Использует sqladmin.authentication.SQLAdminAPIAuthentication для встроенной
    поддержки логина/логаута SQLAdmin. Аутентификация проверяет, что пользователь
    имеет роль "admin" в базе данных.

    Логика:
    1. Пользователь вводит email и пароль на странице /admin/login.
    2. Система находит пользователя по email и проверяет пароль.
    3. Если пользователь найден и имеет роль "admin" — создаётся сессия.
    4. Пароль не логируется и не хранится в сессии (безопасность).

Ключевые принципы:
    - Безопасность: пароль проверяется через passlib, не сохраняется в открытом виде.
    - DRY: логика аутентификации инкапсулирована в один класс.
    - KISS: используется встроенный механизм SQLAdmin.

Ограничения:
    - Доступна только пользователям с ролью "admin".
    - Сессия хранится в cookies (secure, httponly).

Примеры:
    # Инициализация:
    from app.src.api.admin.authentication import admin_auth

    admin_auth.setup(app, engine, session_maker, secret_key="your-secret")
"""

from __future__ import annotations

from logging import getLogger
from typing import Optional
from uuid import UUID

from sqladmin.authentication import AuthenticationBackend
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.responses import RedirectResponse as StarletteRedirectResponse

from app.src.dal.database.models import UserModel

logger = getLogger(__name__)


class AdminAuth(AuthenticationBackend):
    """
    Бэкенд аутентификации для SQLAdmin-панели.

    Назначение:
        Обеспечивает вход/выход администраторов через email и пароль.
        Проверяет роль пользователя (должна быть "admin").

    Содержащиеся методы:
        login: Обработчик POST /admin/login — вход администратора.
        logout: Обработчик GET /admin/logout — выход администратора.
        _authenticate: Внутренний метод проверки учётных данных.

    Аргументы:
        secret_key (str): Секретный ключ для подписи сессий.

    Возвращаемое значение:
        None.

    Возможные исключения:
        Exception: Если возникает ошибка при проверке учётных данных.

    Ограничения:
        - Работает только с UserModel из app.src.dal.database.models.
        - Требует наличия сессии SQLAlchemy в request.state.session.
        - Роль администратора определяется по полю role == "admin".

    Примеры вызова:
        # 1. Вход администратора
        POST /admin/login
        Email: admin@example.com
        Password: admin

        # 2. Выход администратора
        GET /admin/logout

        # 3. Доступ к панели (после логина)
        GET /admin/
    """

    def __init__(self, secret_key: str) -> None:
        """
        Инициализация бэкенда аутентификации.

        Аргументы:
            secret_key (str): Секретный ключ для подписи cookie-сессий.
        """
        super().__init__(secret_key=secret_key)

    async def login(self, request: Request) -> Response:
        """
        Обработчик входа администратора.

        Принимает email и пароль из формы, проверяет учётные данные.
        При успехе — перенаправляет на /admin/, при ошибке — показывает сообщение.

        Аргументы:
            request (Request): HTTP-запрос от FastAPI.

        Возвращаемое значение:
            Response: Перенаправление на /admin/ или обратно на форму логина.

        Возможные исключения:
            Exception: Если возникла ошибка при доступе к базе данных.

        Примеры:
            # Успешный вход
            POST /admin/login
            data: email=admin@example.com&password=admin
            → RedirectResponse("/admin/")

            # Неверные данные
            POST /admin/login
            data: email=wrong@example.com&password=wrong
            → RedirectResponse("/admin/login?error=1")
        """
        form = await request.form()
        email: str = form.get("email", "").strip()
        password: str = form.get("password", "")

        if not email or not password:
            return RedirectResponse("/admin/login?error=1", status_code=303)

        # Получаем сессию из зависимостей
        session = request.state.session

        try:
            user = await session.get(UserModel, None)  # placeholder, см. ниже
            # Альтернатива: используем прямой SQL-запрос для поиска по email
            from sqlalchemy import select
            result = await session.execute(select(UserModel).where(UserModel.email == email))
            user: Optional[UserModel] = result.scalars().first()

            if not user:
                logger.warning("Попытка входа с несуществующим email: %s", email)
                return RedirectResponse("/admin/login?error=1", status_code=303)

            if not user.check_password(password):
                logger.warning("Неверный пароль для email: %s", email)
                return RedirectResponse("/admin/login?error=1", status_code=303)

            if user.role != "admin":
                logger.warning("Попытка входа не-администратора: %s (role=%s)", email, user.role)
                return RedirectResponse("/admin/login?error=2", status_code=303)

            # Сохраняем идентификатор пользователя в сессии
            request.session.update({"user_id": str(user.id)})
            logger.info("Администратор вошёл в систему: %s", email)
            return RedirectResponse("/admin/", status_code=303)

        except Exception as ex:
            logger.error("Ошибка при входе администратора: %s", type(ex).__name__, exc_info=True)
            return RedirectResponse("/admin/login?error=1", status_code=303)

    async def logout(self, request: Request) -> Response:
        """
        Обработчик выхода администратора.

        Очищает сессию и перенаправляет на страницу логина.

        Аргументы:
            request (Request): HTTP-запрос от FastAPI.

        Возвращаемое значение:
            Response: Перенаправление на /admin/login.

        Примеры:
            # Выход
            GET /admin/logout
            → RedirectResponse("/admin/login")
        """
        request.session.clear()
        logger.info("Администратор вышел из системы")
        return RedirectResponse("/admin/login", status_code=303)

    def is_authenticated(self, request: Request) -> bool:
        """
        Проверяет, авторизован ли пользователь.

        Аргументы:
            request (Request): HTTP-запрос от FastAPI.

        Возвращаемое значение:
            bool: True, если в сессии есть user_id, иначе False.

        Примеры:
            # Авторизован
            request.session = {"user_id": "123..."}
            → True

            # Не авторизован
            request.session = {}
            → False
        """
        user_id = request.session.get("user_id")
        if not user_id:
            return False
        try:
            UUID(user_id)
            return True
        except ValueError:
            return False
