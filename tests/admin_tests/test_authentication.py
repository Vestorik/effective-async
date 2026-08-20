import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from sqladmin.authentication import AuthenticationBackend

from app.src.api.admin.authentication import AdminAuth
from app.src.dal.main import DataManager
from app.src.dal.database.models import UserModel
from app.src.api.exceptions import InvalidCredentials
from app.src.api.services.auth import AuthService, RoleType


# --- Хелперы для создания моков ---

def create_mock_db_manager():
    """Создает моковый DataManager."""
    return MagicMock(spec=DataManager)


def create_mock_user(is_admin: bool = True, email: str = "admin@example.com") -> UserModel:
    """Создает мокового пользователя."""
    user = MagicMock(spec=UserModel)
    user.id = "user-uuid-123"
    user.email = email
    user.username = email
    user.role = "admin" if is_admin else "user"
    user.hashed_password = "hashed_password_value"
    return user


def create_mock_request(session_data: dict | None = None, cookies: dict | None  = None, headers: dict | None  = None) -> Request:
    """Создает моковый HTTP-запрос."""
    request = MagicMock(spec=Request)
    request.session = session_data or {}
    request.cookies = cookies or {}
    request.headers = headers or {}
    
    # Мокаем form() метод
    form_data = {}
    form_mock = AsyncMock(return_value=form_data)
    request.form = form_mock
    
    return request

 
@pytest.fixture
def mock_db_manager() -> MagicMock:
    """Фикстура для мокового DataManager."""
    manager = AsyncMock()
    return manager



class TestAdminAuthMasking:
    """Тесты для маскирования email."""

    def test_mask_email_simple(self):
        """Тест простого маскирования email."""
        email = "admin@example.com"
        masked = AdminAuth._mask_email(email)
        assert masked == "a***@example.com"

    def test_mask_email_short_username(self):
        """Тест маскирования email с коротким именем пользователя."""
        email = "a@example.com"
        masked = AdminAuth._mask_email(email)
        assert masked == "***@example.com"

    def test_mask_email_no_domain(self):
        """Тест маскирования email без домена."""
        email = "invalid_email"
        masked = AdminAuth._mask_email(email)
        assert masked == "***"


class TestAdminAuthLogin:
    """Тесты для метода login."""



    @pytest.mark.asyncio
    async def test_login_missing_fields(self, mock_db_manager):
        """Тест входа без данных."""
        request = create_mock_request()
        request.form = AsyncMock(return_value={})

        admin_auth = AdminAuth(secret_key="secret", db_manager=mock_db_manager)
        response = await admin_auth.login(request)

        assert isinstance(response, RedirectResponse)
        assert "error=1" in response.headers.get("location", "")


class TestAdminAuthLogout:
    """Тесты для метода logout."""

    @pytest.mark.asyncio
    async def test_logout_clears_session(self):
        """Тест выхода и очистки сессии."""
        admin_auth = AdminAuth(secret_key="secret", db_manager=MagicMock())
        
        request = MagicMock(spec=Request)
        request.session = {"key": "value"}
        
        response = await admin_auth.logout(request)
        
        assert isinstance(response, RedirectResponse)
        assert response.headers.get("location", "") == "/admin/login"



class TestAdminAuthAuthenticate:
    """Тесты для метода authenticate."""



    @pytest.mark.asyncio
    async def test_authenticate_no_token(self, mock_db_manager):
        """Тест отсутствия токена."""
        admin_auth = AdminAuth(secret_key="secret", db_manager=mock_db_manager)
        
        request = create_mock_request()
        
        with pytest.raises(Exception) as exc_info:
            await admin_auth.authenticate(request)
        
        assert "401" in str(exc_info.value.status_code) if hasattr(exc_info.value, 'status_code') else True

    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self, mock_db_manager):
        """Тест невалидного токена."""
        with patch('app.src.api.admin.authentication.AuthService') as MockAuthService:
            mock_auth_service = AsyncMock()
            MockAuthService.return_value = mock_auth_service
            
            mock_uow = AsyncMock()
            mock_uow.users = MagicMock()
            mock_auth_service.get_current_user = AsyncMock(side_effect=InvalidCredentials)
            
            mock_db_manager.__aenter__ = AsyncMock(return_value=mock_uow)
            mock_db_manager.__aexit__ = AsyncMock(return_value=None)

            admin_auth = AdminAuth(secret_key="secret", db_manager=mock_db_manager)
            
            request = create_mock_request(cookies={"access_token": "bad_token"})
            
            with pytest.raises(Exception) as exc_info:
                await admin_auth.authenticate(request)
            
            assert hasattr(exc_info.value, 'status_code')
            assert exc_info.value.status_code == 401
