"""
Конфигурация и инициализация SQLAdmin админ-панели.

Назначение:
    Предоставляет центральный интерфейс для подключения SQLAdmin к FastAPI-приложению.

    Содержит:
    - SQLAdminViewSet: класс-контейнер для настройки админ-панели.
    - admin_view_set: глобальный экземпляр, готовый к использованию.

    Функционал:
    - Регистрация всех моделей (из models.py) в SQLAdmin.
    - Настройка аутентификации (из authentication.py).
    - Подключение шаблонов (из app/templates).
    - Настройка CORS и basePath.

Архитектура:
    - SQLAdminViewSet: инкапсулирует SQLAdmin, authentication backend и настройки.
    - setup(): метод для инициализации админ-панели на FastAPI-приложении.
    - dependency: get_admin_session — провайдер зависимостей для сессии БД.

Ключевые принципы:
    - DRY: настройка в одном месте,多处 использование.
    - KISS: простой интерфейс setup() с минимальным количеством параметров.
    - Dependency Injection: сессия БД внедряется через FastAPI dependencies.

Ограничения:
    - Требуется, чтобы FastAPI-приложение было инициализировано ранее.
    - engine и session_maker должны быть доступны через app.state.
    - secret_key должен быть задан (не None).

Примеры:
    # 1. В lifespan.py или main.py:
    from app.src.api.admin import admin_view_set

    admin_view_set.setup(
        app=MAIN_APP,
        secret_key="your-secret-key-here",
    )
    app.include_router(admin_view_set.admin.urls)
"""

from __future__ import annotations

from logging import getLogger
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sqladmin import Admin

from app.src.api.admin.authentication import AdminAuth
from app.src.api.admin.models import ADMIN_VIEW_LIST

logger = getLogger(__name__)


# =============================================================================
# Зависимость: сессия БД для аутентификации
# =============================================================================

async def get_admin_session(request: Request) -> AsyncSession:
    """
    Зависимость FastAPI для получения асинхронной сессии БД.

    Назначение:
        Предоставляет сессию SQLAlchemy для эндпоинтов аутентификации админ-панели.

    Аргументы:
        request (Request): HTTP-запрос от FastAPI.

    Возвращаемое значение:
        AsyncSession: Асинхронная сессия базы данных.

    Возможные исключения:
        RuntimeError: Если data_manager не инициализирован в app.state.

    Примеры:
        # FastAPI автоматически вызовет эту функцию при регистрации зависимости
        @app.dependency_override(...)
    """
    data_manager = request.app.state.data_manager
    if not hasattr(data_manager, "_DataManager__database"):
        raise RuntimeError("DataManager не инициализирован. Проверьте lifespan.")

    uow = data_manager()
    async with uow as session_uow:
        yield session_uow.session


# =============================================================================
# ViewSet админ-панели
# =============================================================================

class SQLAdminViewSet:
    """
    Набор настроек и компонентов для SQLAdmin админ-панели.

    Назначение:
        Инкапсулирует все компоненты админ-панели:
        - SQLAdmin instance.
        - Бэкенд аутентификации.
        - Список моделей для управления.

    Содержащиеся методы:
        setup: Инициализация SQLAdmin на FastAPI-приложении.
        _register_views: Регистрация всех моделей в SQLAdmin.

    Аргументы:
        None (настраивается через метод setup()).

    Возвращаемое значение:
        None.

    Возможные исключения:
        ValueError: Если app или secret_key не переданы в setup().
        RuntimeError: Если админ-панель уже была инициализирована.

    Ограничения:
        - app должен иметь state.data_manager с инициализированным DataManager.
        - secret_key не может быть пустым.
        - Админ-панель инициализируется один раз.

    Примеры вызова:
        # 1. Инициализация
        admin_view_set.setup(
            app=MAIN_APP,
            secret_key="super-secret-key",
        )

        # 2. Подключение роутера
        MAIN_APP.include_router(admin_view_set.admin.urls)

        # 3. Доступ к панели
        #   GET /admin/       — главная страница
        #   GET /admin/login  — страница входа
        #   GET /admin/logout — выход
    """

    def __init__(self) -> None:
        """Инициализация пустого ViewSet. Модель и аутентификация настраиваются через setup()."""
        self.admin: Optional[Admin] = None
        self.auth: Optional[AdminAuth] = None

    def setup(
        self,
        app: object,
        secret_key: str,
        database_url: Optional[str] = None,
    ) -> None:
        """
        Инициализирует SQLAdmin на FastAPI-приложении.

        Назначение:
            Создаёт экземпляры Admin и AdminAuth, регистрирует модели,
            настраивает basePath и template folders.

        Аргументенты:
            app: FastAPI-приложение (объект FastAPI).
            secret_key (str): Секретный ключ для подписи cookie-сессий аутентификации.
            database_url (Optional[str]): URL базы данных (опционально, для отображения в UI).

        Возвращаемое значение:
            None.

        Возможные исключения:
            ValueError: Если secret_key пустой.
            RuntimeError: Если админ-панель уже была инициализирована.

        Ограничения:
            - app должен быть экземпляром FastAPI.
            - secret_key должен быть непустой строкой.
            - Вызывается один раз во время запуска приложения.

        Примеры:
            # 1. Базовая инициализация
            admin_view_set.setup(app, secret_key="my-secret")

            # 2. С указанием database_url
            admin_view_set.setup(
                app,
                secret_key="my-secret",
                database_url="postgresql+asyncpg://user:pass@localhost/db"
            )
        """
        if not secret_key:
            raise ValueError("secret_key не может быть пустым")

        if self.admin is not None:
            raise RuntimeError("Админ-панель уже инициализирована")

        # Создаём бэкенд аутентификации
        self.auth = AdminAuth(secret_key=secret_key)

        # Создаём SQLAdmin
        self.admin = Admin(
            app=app,
            secret_key=secret_key,
            base_url="/admin",
            login_view="/admin/login",
            authentication_backend=self.auth,
        )

        # Настраиваем папку шаблонов
        try:
            from pathlib import Path
            templates_path = Path(__file__).resolve().parents[3] / "templates"
            if templates_path.exists():
                from fastapi.templating import Jinja2Templates
                self.admin.templates_dir = str(templates_path)
                logger.info("Папка шаблонов админ-панели: %s", templates_path)
        except Exception as ex:
            logger.warning("Не удалось настроить папку шаблонов: %s", ex)

        # Регистрируем модели
        self._register_views()

        logger.info("SQLAdmin админ-панель инициализирована (basePath=/admin)")

    def _register_views(self) -> None:
        """
        Регистрирует все модели в SQLAdmin.

        Назначение:
            Проходит по списку ADMIN_VIEW_LIST и добавляет каждое представление
            в SQLAdmin через admin.add_view().

        Возвращаемое значение:
            None.

        Примеры:
            # Вызывается автоматически при setup()
            admin_view_set._register_views()
            # → регистрирует UserModelView, TeamModelView, и т.д.
        """
        if not self.admin:
            raise RuntimeError("Сначала вызовите setup()")

        for view_class in ADMIN_VIEW_LIST:
            self.admin.add_view(view_class)
            logger.debug("Зарегистрировано представление: %s", view_class.name)

        logger.info("Зарегистрировано %d моделей в SQLAdmin", len(ADMIN_VIEW_LIST))


# =============================================================================
# Глобальный экземпляр
# =============================================================================

admin_view_set = SQLAdminViewSet()
