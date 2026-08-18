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
from app.src.dal.main import DataManager
from app.src.api.exceptions import InvalidCredentials

from logging import getLogger
from uuid import UUID

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from sqladmin.authentication import AuthenticationBackend

from app.src.api.services.auth import pwd_context, AuthService, RoleType
from app.src.api.utils.api_utils import get_data_manager
from app.src.dal.database.models import UserModel

logger = getLogger(__name__)


class AdminAuth(AuthenticationBackend):
    """
    Бэкенд аутентификации для SQLAdmin-панели.

    Назначение:app/src/api/services/auth.py
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
    db_manager: DataManager

    def __init__(self, secret_key: str, db_manager: DataManager) -> None:
        """
        Инициализация бэкенда аутентификации.

        Аргументы:
            secret_key (str): Секретный ключ для подписи cookie-сессий.
        """
        self.db_manager: DataManager=db_manager
        super().__init__(secret_key=secret_key)

    async def login(self, request: Request) -> Response:
        """
        Обработчик входа администратора.

        Назначение:
            Реализует механизм входа через email/пароль. Проверяет роль пользователя.

        Содержащиеся методы:
            (внутренняя логика проверки)

        Аргументы:
            request: Request - HTTP-запрос от FastAPI с формой логина.

        Возвращаемое значение:
            Response - Перенаправление (303) на главную страницу админки или на страницу логина с ошибкой.

        Возможные исключения:
            Exception: Ошибки базы данных или сессии.

        Ограничения:
            - Требует наличия зависимости session в request.state.
            - Не реализована защита от brute-force (time-out/rate-limit).

        Примеры:
            # Успешный вход
            POST /admin/login
            data: email=admin@example.com&password=admin
            → RedirectResponse("/admin/")
        """
        form = await request.form()
        email: str = form.get("username", "").strip()  # ty: ignore[unresolved-attribute]
        password: str = form.get("password", "")  # ty: ignore[invalid-assignment]
        
        if not email:
            logger.warning("Нет email")
            return RedirectResponse("/admin/login?error=1", status_code=303)
        elif not password:
            logger.warning("Нет password")
            return RedirectResponse("/admin/login?error=1", status_code=303)

        # Получаем сессию из зависимостей

        try:
            # Используем AuthService для проверки учётных данных
            async with self.db_manager()as uow:
                user= await uow.users.get_by_email(email)
                

            if not user:
                logger.warning("Попытка входа с несуществующим email: %s", self._mask_email(email))
                return RedirectResponse("/admin/login?error=1", status_code=303)

            if not pwd_context.verify(password, user.hashed_password):
                logger.warning("Неверный пароль для пользователя: %s", self._mask_email(email))
                return RedirectResponse("/admin/login?error=2", status_code=303)

            if user.role != "admin":
                logger.warning("Попытка входа не-администратора: %s", self._mask_email(email))
                return RedirectResponse("/admin/login?error=3", status_code=303)
            
            tokens = AuthService().generate_cookie_token(user)
            redirect_response = RedirectResponse("/admin/", status_code=303)
            
            # Устанавливаем куки напрямую на ответ редиректа
            redirect_response.set_cookie(
                key="access_token",
                value=tokens["access_token"], 
                httponly=True,
                secure=True,       
                samesite="lax",   
                max_age=tokens["durationin_sec"]
            )

            logger.info("Администратор вошёл в систему: %s", email)
            return redirect_response



        except Exception as ex:
            logger.exception("Ошибка при входе администратора: %s", type(ex).__name__)
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

    async def authenticate(self, request: Request) -> bool:
        """
        Проверяет, авторизован ли пользователь в текущей сессии.

        Аргументы:
            request (Request): HTTP-запрос от FastAPI.

        Возвращаемое значение:
            bool: True, если пользователь авторизован и имеет роль admin, иначе False.

        Примеры:
            # Авторизован
            request.session = {"user_id": "uuid"}
            → True

            # Не авторизован
            request.session = {}
            → False
        """

        auth_header = request.headers.get("Authorization")
        token = None
        
        if auth_header:
            # Проверяем формат "Bearer <token>"
            parts = auth_header.split(" ", 1)
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]
        

        if not token:
            token = request.cookies.get("access_token")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Не авторизован: токен не найден",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        try:
            async with self.db_manager() as uow:
                auth_service = AuthService()
                user = await auth_service.get_current_user(uow.users, token)
                if user.role == RoleType.ADMIN.value:
                    return True

        except InvalidCredentials:

            logger.info("Неверный или просроченный токен") 
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный или просроченный токен",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception:
            logger.exception("Ошибка сервера при проверке токена")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Ошибка сервера при проверке токена",
                headers={"WWW-Authenticate": "Bearer"},)
            
        return False


    @staticmethod
    def _mask_email(email: str) -> str:
        """
        Маскирует email для логирования.

        Аргументы:
            email (str): Исходный email.

        Возвращаемое значение:
            str: За masked email.

        Примеры:
            >>> AdminAuth._mask_email("admin@example.com")
            'a***@example.com'
        """
        if '@' in email:
            username, domain = email.split('@', 1)
            masked_username = f"{username[0]}***" if len(username) > 1 else "***"
            return f"{masked_username}@{domain}"
        return "***"