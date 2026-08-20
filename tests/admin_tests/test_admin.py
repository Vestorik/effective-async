import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine
from sqladmin import Admin

from app.src.api.admin.admin import SQLAdminViewSet
from app.src.api.admin.authentication import AdminAuth
from app.src.dal.main import DataManager


# --- Хелперы для создания моков ---

def create_mock_app() -> FastAPI:
    """Создает моковый экземпляр FastAPI."""
    app = MagicMock(spec=FastAPI)
    return app


def create_mock_engine() -> AsyncEngine:
    """Создает моковый экземпляр AsyncEngine."""
    engine = MagicMock(spec=AsyncEngine)
    return engine


def create_mock_db_manager() -> DataManager:
    """Создает моковый экземпляр DataManager."""
    manager = MagicMock(spec=DataManager)
    return manager


def create_mock_admin_auth() -> MagicMock:
    """Создает моковый экземпляр AdminAuth."""
    auth = MagicMock(spec=AdminAuth)
    return auth


def create_mock_admin() -> MagicMock:
    """Создает моковый экземпляр Admin."""
    admin = MagicMock(spec=Admin)
    return admin


# --- Фикстуры ---

@pytest.fixture
def mock_app() -> FastAPI:
    """Фикстура для мокового FastAPI приложения."""
    return create_mock_app()


@pytest.fixture
def mock_engine() -> AsyncEngine:
    """Фикстура для мокового AsyncEngine."""
    return create_mock_engine()


@pytest.fixture
def mock_db_manager() -> DataManager:
    """Фикстура для мокового DataManager."""
    return create_mock_db_manager()


@pytest.fixture
def mock_admin_view_class():
    """Фикстура для мокового класса представления."""
    view_class = MagicMock()
    view_class.name = "TestView"
    return view_class


class TestSQLAdminViewSet:
    """Тесты для SQLAdminViewSet."""

    def test_init_raises_error_on_empty_secret_key(self, mock_app, mock_engine, mock_db_manager):
        """Тест выброса исключения при пустом secret_key."""
        with pytest.raises(ValueError, match="secret_key не может быть пустым"):
            SQLAdminViewSet(
                app=mock_app,
                secret_key="",
                databse_engine=mock_engine,
                db_manager=mock_db_manager
            )

    def test_init_creates_auth_and_admin(self, mock_app, mock_engine, mock_db_manager):
        """Тест успешной инициализации ViewSet."""
        with patch('app.src.api.admin.admin.AdminAuth') as MockAuth:
            with patch('app.src.api.admin.admin.Admin') as MockAdmin:
                mock_auth_instance = create_mock_admin_auth()
                mock_admin_instance = create_mock_admin()
                
                MockAuth.return_value = mock_auth_instance
                MockAdmin.return_value = mock_admin_instance

                view_set = SQLAdminViewSet(
                    app=mock_app,
                    secret_key="test_secret",
                    databse_engine=mock_engine,
                    db_manager=mock_db_manager
                )

                # Проверка создания Auth
                MockAuth.assert_called_once_with(secret_key="test_secret", db_manager=mock_db_manager)
                
                # Проверка создания Admin
                MockAdmin.assert_called_once_with(
                    app=mock_app,
                    base_url="/admin",
                    engine=mock_engine,
                    authentication_backend=mock_auth_instance,
                )
                
                assert view_set.auth is mock_auth_instance
                assert view_set.admin is mock_admin_instance

    @pytest.mark.asyncio
    async def test_register_views_registers_all_models(self, mock_app, mock_engine, mock_db_manager):
        """Тест регистрации всех представлений из ADMIN_VIEW_LIST."""
        # Мокаем модели, чтобы избежать импорта и проблем с зависимостями
        mock_view1 = MagicMock()
        mock_view1.name = "UserView"
        
        mock_view2 = MagicMock()
        mock_view2.name = "TeamView"
        
        mock_views = [mock_view1, mock_view2]
        
        with patch('app.src.api.admin.admin.ADMIN_VIEW_LIST', mock_views):
            with patch('app.src.api.admin.admin.AdminAuth') as MockAuth:
                with patch('app.src.api.admin.admin.Admin') as MockAdmin:
                    mock_auth_instance = create_mock_admin_auth()
                    mock_admin_instance = create_mock_admin()
                    
                    MockAuth.return_value = mock_auth_instance
                    MockAdmin.return_value = mock_admin_instance

                    view_set = SQLAdminViewSet(
                        app=mock_app,
                        secret_key="test_secret",
                        databse_engine=mock_engine,
                        db_manager=mock_db_manager
                    )
                    
                    # _register_views вызывается внутри __init__
                    # Проверяем, что add_view был вызван для каждого представления
                    assert mock_admin_instance.add_view.call_count == 2
                    mock_admin_instance.add_view.assert_any_call(mock_view1)
                    mock_admin_instance.add_view.assert_any_call(mock_view2)

    @pytest.mark.asyncio
    async def test_register_views_logs_info(self, mock_app, mock_engine, mock_db_manager):
        """Тест логирования количества зарегистрированных моделей."""
        mock_view = MagicMock()
        mock_view.name = "SingleView"
        
        with patch('app.src.api.admin.admin.ADMIN_VIEW_LIST', [mock_view]):
            with patch('app.src.api.admin.admin.AdminAuth') as MockAuth:
                with patch('app.src.api.admin.admin.Admin') as MockAdmin:
                    with patch('app.src.api.admin.admin.logger') as MockLogger:
                        mock_auth_instance = create_mock_admin_auth()
                        mock_admin_instance = create_mock_admin()
                        
                        MockAuth.return_value = mock_auth_instance
                        MockAdmin.return_value = mock_admin_instance

                        view_set = SQLAdminViewSet(
                            app=mock_app,
                            secret_key="test_secret",
                            databse_engine=mock_engine,
                            db_manager=mock_db_manager
                        )
                        
                        found_registration_log = False
                        for call in MockLogger.info.call_args_list:
                            # call.args - позиционные аргументы, call.kwargs - именованные
                            # Ожидаем вызов вида: logger.info("Зарегистрировано %d моделей в SQLAdmin", 1)
                            if call.args and isinstance(call.args[0], str):
                                if "Зарегистрировано" in call.args[0] and "SQLAdmin" in call.args[0]:
                                    found_registration_log = True
                                    break
                        
                        assert found_registration_log, "Логирующая запись о регистрации моделей не найдена"

    @pytest.mark.asyncio
    async def test_register_views_raises_when_admin_is_none(self, mock_app, mock_engine, mock_db_manager):
        """Тест выброса исключения, если admin инициализирован не был."""
        # Создаем инстанс, но вручную установим admin = None
        with patch('app.src.api.admin.admin.AdminAuth') as MockAuth:
            with patch('app.src.api.admin.admin.Admin') as MockAdmin:
                mock_auth_instance = create_mock_admin_auth()
                MockAuth.return_value = mock_auth_instance
                
                # Мокаем Admin так, чтобы он возвращал None для проверки условия,
                # но так как admin создается в __init__, проще протестировать логику метода напрямую
                
                view_set = SQLAdminViewSet(
                    app=mock_app,
                    secret_key="test_secret",
                    databse_engine=mock_engine,
                    db_manager=mock_db_manager
                )
                
                # Симулируем ошибку: admin стал None
                view_set.admin = None
                
                with pytest.raises(RuntimeError, match="self.admin Не может быть None!"):
                    view_set._register_views()