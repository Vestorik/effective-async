
from __future__ import annotations

from logging import getLogger

from fastapi import FastAPI
from sqladmin import Admin
from sqlalchemy.ext.asyncio import AsyncEngine

from app.src.api.admin.authentication import AdminAuth
from app.src.api.admin.models import ADMIN_VIEW_LIST
from app.src.dal.main import DataManager

logger = getLogger(__name__)


class SQLAdminViewSet:

    auth: AdminAuth | None = None
    admin: Admin | None = None


    def __init__(
        self,
        app: FastAPI,
        secret_key: str,
        databse_engine: AsyncEngine,
        db_manager : DataManager
        ) -> None:
        """Инициализация пустого ViewSet. Модель и аутентификация настраиваются через setup()."""
        if not secret_key:
            raise ValueError("secret_key не может быть пустым")

        if self.admin is not None:
            raise RuntimeError("Админ-панель уже инициализирована")

        # Создаём бэкенд аутентификации
        self.auth = AdminAuth(secret_key=secret_key, db_manager=db_manager)


        # Создаём SQLAdmin
        self.admin = Admin(
            app=app,
            base_url="/admin",
            engine=databse_engine,
            authentication_backend=self.auth,
        )
        
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
            raise RuntimeError("self.admin Не может быть None!")

        for view_class in ADMIN_VIEW_LIST:
            self.admin.add_view(view_class)
            logger.debug("Зарегистрировано представление: %s", view_class.name)

        logger.info("Зарегистрировано %d моделей в SQLAdmin", len(ADMIN_VIEW_LIST))


