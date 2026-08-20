from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import jwt
import pytest

from app.src.api.exceptions import InvalidCredentials, UserNotFound

# Импортируем сущности из приложения
from app.src.api.services.auth import (
    MAIN_AUTH_CONFIG,
    AuthService,
)
from app.src.api.shems import UserCreateSheme, UserOutSheme
from app.src.base.config import AuthConfig
from app.src.dal.database.models import UserModel

# --- Моки и Константы ---

# Генерация фиктивных данных
FAKE_EMAIL = "test@example.com"
FAKE_PASSWORD = "secure_password_123"
FAKE_USERNAME = "testuser"
FAKE_SECRET_KEY = "my_super_secret_key_for_jwt_signing_12345"
FAKE_REFRESH_TOKEN_SECRET = "my_refresh_secret_key_12345"

# Настройки аутентификации для тестов
TEST_AUTH_CONFIG = AuthConfig(
    secret_key=FAKE_SECRET_KEY,
    token_expiry_minutes=30,
    refresh_token_expiry_days=7,
    algorithm="HS256"
)


@pytest.fixture
def auth_config():
    """Возвращает тестовую конфигурацию аутентификации."""
    return TEST_AUTH_CONFIG


@pytest.fixture
def mock_user_model():
    """
    Создает мок UserModel с необходимыми полями.
    
    Важно: MagicMock с spec=UserModel не будет автоматически прокидывать атрибуты,
    если они не установлены явно. В тестах мы будем устанавливать их перед вызовами.
    """
    user_id = uuid4()
    user = MagicMock(spec=UserModel)
    user.id = user_id
    user.email = FAKE_EMAIL
    user.username = FAKE_USERNAME
    user.role = "user"
    user.hashed_password = None
    user.team_id = None
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    user.refresh_token_hash = None
    return user


@pytest.fixture
def mock_user_repo():
    """Создает мок UserRepository."""
    repo = AsyncMock()
    # По умолчанию get_by_email возвращает None
    repo.get_by_email = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def auth_service(auth_config):
    """Создает экземпляр AuthService с тестовой конфигурацией."""
    return AuthService(auth_config=auth_config)


class TestAuthService:
    """Тесты для класса AuthService."""

    def test_init_with_default_config(self):
        """Тест инициализации по умолчанию."""
        service = AuthService()
        assert service.secret_key == MAIN_AUTH_CONFIG.secret_key
        assert service.token_expiry_minutes == MAIN_AUTH_CONFIG.token_expiry_minutes
        assert service.auth_algorithm == MAIN_AUTH_CONFIG.algorithm

    def test_init_with_custom_config(self, auth_config):
        """Тест инициализации с кастомной конфигурацией."""
        service = AuthService(auth_config=auth_config)
        assert service.secret_key == FAKE_SECRET_KEY
        assert service.token_expiry_minutes == 30
        assert service.auth_algorithm == "HS256"

    @pytest.mark.asyncio
    async def test_register_success(self, auth_service, mock_user_repo, mock_user_model):
        """Успешная регистрация пользователя."""
        user_data = UserCreateSheme(
            email=FAKE_EMAIL,
            password=FAKE_PASSWORD,
            username=FAKE_USERNAME,
            role="user",
            team_id=None
        )
        
        # Мокаем поведение create: заполняем мок модели данными, как будто они пришли из БД
        async def capture_user(user_obj):
            mock_user_model.id = uuid4()
            mock_user_model.hashed_password = user_obj.hashed_password
            mock_user_model.email = user_obj.email
            mock_user_model.username = user_obj.username
            mock_user_model.role = user_obj.role
            mock_user_model.team_id = user_obj.team_id
            
        mock_user_repo.create = AsyncMock(side_effect=capture_user)
        
        result = await auth_service.register(mock_user_repo, user_data)
        
        assert isinstance(result, UserOutSheme)
        assert result.email == FAKE_EMAIL
        assert result.username == FAKE_USERNAME
        mock_user_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_existing_user(self, auth_service, mock_user_repo):
        """Регистрация пользователя с уже занятым email (эмуляция исключения от БД/Репозитория)."""
        from app.src.api.exceptions import UserAlreadyExists
        
        user_data = UserCreateSheme(
            email="existing@example.com",
            password=FAKE_PASSWORD,
            username="existing",
            role="user",
            team_id=None
        )
        
        mock_user_repo.create = AsyncMock(side_effect=UserAlreadyExists())
        
        with pytest.raises(UserAlreadyExists):
            await auth_service.register(mock_user_repo, user_data)

    def test_generate_cookie_token(self, auth_service, mock_user_model):
        """Генерация JWT токена."""
        mock_user_model.id = uuid4()
        mock_user_model.email = FAKE_EMAIL
        mock_user_model.role = "user"
        
        result = auth_service.generate_cookie_token(mock_user_model)
        
        assert "access_token" in result
        assert result["token_type"] == "bearer"
        assert "durationin_sec" in result
        assert result["durationin_sec"] == auth_service.token_expiry_minutes * 60
        
        import jwt
        payload = jwt.decode(result["access_token"], auth_service.secret_key, algorithms=["HS256"])
        assert payload["sub"] == str(mock_user_model.id)
        assert payload["email"] == FAKE_EMAIL

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_service, mock_user_repo, mock_user_model):
        """Успешная аутентификация."""
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
        
        hashed = pwd_context.hash(FAKE_PASSWORD)
        mock_user_model.hashed_password = hashed
        
        mock_user_repo.get_by_email = AsyncMock(return_value=mock_user_model)
        
        result = await auth_service.authenticate(mock_user_repo, FAKE_EMAIL, FAKE_PASSWORD)
        
        assert "access_token" in result
        mock_user_repo.get_by_email.assert_called_once_with(FAKE_EMAIL)

    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, auth_service, mock_user_repo, mock_user_model):
        """Неверный пароль."""
        # Используем passlib для генерации корректного хэша другого пароля.
        # Это гарантирует, что passlib сможет распознать алгоритм при проверке.
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
        
        # Генерируем хэш для "другого" пароля
        other_password_hash = pwd_context.hash("different_password")
        mock_user_model.hashed_password = other_password_hash
        
        mock_user_repo.get_by_email = AsyncMock(return_value=mock_user_model)
        
        # Пытаемся авторизоваться с исходным паролем, который не совпадет с хэшем
        with pytest.raises(InvalidCredentials):
            await auth_service.authenticate(mock_user_repo, FAKE_EMAIL, FAKE_PASSWORD)

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service, mock_user_repo):
        """Пользователь не найден."""
        mock_user_repo.get_by_email = AsyncMock(return_value=None)
        
        with pytest.raises(InvalidCredentials):
            await auth_service.authenticate(mock_user_repo, FAKE_EMAIL, FAKE_PASSWORD)

    @pytest.mark.asyncio
    async def test_verify_token_success(self, auth_service, mock_user_model):
        """Проверка валидности токена."""
        # Генерируем валидный токен
        token_data = auth_service.generate_cookie_token(mock_user_model)
        token = token_data["access_token"]
        
        payload = await auth_service.verify_token(token)
        
        assert payload["sub"] == str(mock_user_model.id)
        assert payload["email"] == FAKE_EMAIL

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_service):
        """Проверка невалидного токена."""
        with pytest.raises(InvalidCredentials):
            await auth_service.verify_token("invalid.token.here")

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, auth_service, mock_user_repo, mock_user_model):
        """Получение текущего пользователя по токену."""
        # Генерируем токен
        token_data = auth_service.generate_cookie_token(mock_user_model)
        token = token_data["access_token"]
        
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user_model)
        
        user = await auth_service.get_current_user(mock_user_repo, token)
        
        assert user.id == mock_user_model.id
        mock_user_repo.get_by_id.assert_called_once_with(mock_user_model.id)

    @pytest.mark.asyncio
    async def test_get_current_user_user_not_found(self, auth_service, mock_user_repo):
        """Пользователь не найден в БД по ID из токена."""
        # Создаем токен с несуществующим ID
        from datetime import datetime, timedelta

        import jwt
        payload = {
            "sub": str(uuid4()),
            "email": "ghost@example.com",
            "role": "user",
            "exp": datetime.now(UTC) + timedelta(hours=1)
        }
        token = jwt.encode(payload, FAKE_SECRET_KEY, algorithm="HS256")
        
        mock_user_repo.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(UserNotFound):
            await auth_service.get_current_user(mock_user_repo, token)

    @pytest.mark.asyncio
    async def test_get_token_expiry(self, auth_service):
        """Получение срока действия токена."""
        from datetime import datetime, timedelta

        import jwt
        
        expires = datetime.now(UTC) + timedelta(hours=1)
        payload = {
            "sub": str(uuid4()),
            "exp": expires,
        }
        token = jwt.encode(payload, FAKE_SECRET_KEY, algorithm="HS256")
        
        exp_dt = await auth_service.get_token_expiry(token)
        
        assert abs((exp_dt - expires).total_seconds()) < 1.0
        assert isinstance(exp_dt, datetime)
        
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, auth_service, mock_user_repo, mock_user_model):
        """Обновление токена."""
        # 1. Создаем старый refresh_token и хэш
        old_refresh_payload = {
            "sub": str(mock_user_model.id),
            "type": "refresh",
            "exp": datetime.now(UTC) + timedelta(days=7)
        }
        old_refresh_token = jwt.encode(old_refresh_payload, FAKE_SECRET_KEY, algorithm="HS256")
        
        from passlib.handlers.argon2 import argon2
        mock_user_model.refresh_token_hash = argon2.hash(old_refresh_token)
        
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user_model)
        
        # 2. Вызываем refresh
        result = await auth_service.refresh_token(mock_user_repo, old_refresh_token)
        
        # 3. Проверки
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        
        # Проверка, что хэш обновился
        # (так как мы передали тот же старый токен, хэш должен обновиться на его новый хэш)
        mock_user_repo.update.assert_called_once()

