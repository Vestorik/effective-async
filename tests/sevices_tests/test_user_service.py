"""Тесты для UserService: create, get_user_by_id, get_user_by_email, get_all_users, update_user, delete_user.

Покрытые кейсы:
- create: success, email already exists
- get_user_by_id: found, not found
- get_user_by_email: found, not found
- get_all_users: с пагинацией и без
- update_user: success (все поля, частичное), not found
- delete_user: success, not found
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID
from datetime import datetime

from app.src.api.services.user_service import UserService
from app.src.api.exceptions import UserNotFound, UserAlreadyExists
from app.src.dal.database.repositories import UserRepository
from app.src.dal.database.models import UserModel
from app.src.api.shems import UserCreateSheme, UserUpdateSheme, UserOutSheme


def create_mock_user(
    user_id: UUID | None = None,
    username: str = "testuser",
    email: str = "test@example.com",
    role: str = "user",
    team_id: UUID | None = None,
    hashed_password: str = "$argon2id$v=19$m=65536,t=3,p=1$...",
) -> UserModel:
    """Создает мок UserModel для тестов."""
    user = MagicMock(spec=UserModel)
    user.id = user_id or uuid4()
    user.username = username
    user.email = email
    user.role = role
    user.team_id = team_id
    user.hashed_password = hashed_password
    user.created_at = datetime.now()
    user.updated_at = datetime.now()
    user._sa_instance_state = MagicMock()
    return user


@pytest.fixture
def user_service() -> UserService:
    """Экземпляр UserService."""
    return UserService()


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Моковый UserRepository."""
    repo = AsyncMock(spec=UserRepository)
    return repo


class TestUserServiceCreate:
    """Тесты для метода create."""

    @pytest.mark.asyncio
    async def test_create_success(self, user_service, mock_user_repo):
        """Успешное создание пользователя."""
        user_data = UserCreateSheme(
            username="newuser",
            email="new@example.com",
            password="securepass123",
            role="user",
        )
        mock_user_repo.get_by_email = AsyncMock(return_value=None)
        mock_user = create_mock_user(email="new@example.com")
        mock_user_repo.create = AsyncMock(return_value=mock_user)

        result = await user_service.create(mock_user_repo, user_data)

        assert result is not None
        assert isinstance(result, UserOutSheme)
        assert result.username == "newuser"
        assert result.email == "new@example.com"
        mock_user_repo.get_by_email.assert_called_once_with("new@example.com")
        mock_user_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_email_exists(self, user_service, mock_user_repo):
        """Создание пользователя с существующим email."""
        user_data = UserCreateSheme(
            username="newuser",
            email="exists@example.com",
            password="securepass123",
            role="user",
        )
        existing_user = create_mock_user(email="exists@example.com")
        mock_user_repo.get_by_email = AsyncMock(return_value=existing_user)

        with pytest.raises(UserAlreadyExists):
            await user_service.create(mock_user_repo, user_data)

        mock_user_repo.create.assert_not_called()


class TestUserServiceGetUserById:
    """Тесты для метода get_user_by_id."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, user_service, mock_user_repo):
        """Получение пользователя по существующему ID."""
        user_id = uuid4()
        mock_user = create_mock_user(user_id)
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        result = await user_service.get_user_by_id(mock_user_repo, user_id)

        assert result is not None
        assert isinstance(result, UserOutSheme)
        assert result.username == mock_user.username
        mock_user_repo.get_by_id.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_service, mock_user_repo):
        """Получение пользователя с несуществующим ID."""
        user_id = uuid4()
        mock_user_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(UserNotFound):
            await user_service.get_user_by_id(mock_user_repo, user_id)


class TestUserServiceGetUserByEmail:
    """Тесты для метода get_user_by_email."""

    @pytest.mark.asyncio
    async def test_get_user_by_email_found(self, user_service, mock_user_repo):
        """Получение пользователя по существующему email."""
        mock_user = create_mock_user(email="found@example.com")
        mock_user_repo.get_by_email = AsyncMock(return_value=mock_user)

        result = await user_service.get_user_by_email(mock_user_repo, "found@example.com")

        assert result is not None
        assert isinstance(result, UserOutSheme)
        assert result.email == "found@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, user_service, mock_user_repo):
        """Получение пользователя с несуществующим email."""
        mock_user_repo.get_by_email = AsyncMock(return_value=None)

        result = await user_service.get_user_by_email(mock_user_repo, "none@example.com")

        assert result is None


class TestUserServiceGetAllUsers:
    """Тесты для метода get_all_users."""

    @pytest.mark.asyncio
    async def test_get_all_users_default_pagination(self, user_service, mock_user_repo):
        """Получение пользователей по умолчанию."""
        users = [create_mock_user(), create_mock_user(username="user2")]
        mock_user_repo.get_all_paginated = AsyncMock(return_value=(users, 2))

        result, total = await user_service.get_all_users(mock_user_repo)

        assert len(result) == 2
        assert total == 2
        assert all(isinstance(u, UserOutSheme) for u in result)

    @pytest.mark.asyncio
    async def test_get_all_users_with_role_filter(self, user_service, mock_user_repo):
        """Получение пользователей с фильтром по роли."""
        users = [create_mock_user(role="admin")]
        mock_user_repo.get_all_paginated = AsyncMock(return_value=(users, 1))

        result, total = await user_service.get_all_users(
            mock_user_repo, page=1, page_size=10, role="admin"
        )

        assert len(result) == 1
        assert result[0].role == "admin"
        mock_user_repo.get_all_paginated.assert_called_once_with(
            page=1, page_size=10, role="admin"
        )

    @pytest.mark.asyncio
    async def test_get_all_users_empty(self, user_service, mock_user_repo):
        """Получение пустого списка пользователей."""
        mock_user_repo.get_all_paginated = AsyncMock(return_value=([], 0))

        result, total = await user_service.get_all_users(mock_user_repo)

        assert len(result) == 0
        assert total == 0


class TestUserServiceUpdateUser:
    """Тесты для метода update_user."""

    @pytest.mark.asyncio
    async def test_update_user_success_full(self, user_service, mock_user_repo):
        """Полное обновление пользователя."""
        user_id = uuid4()
        mock_user = create_mock_user(user_id, username="old", email="old@example.com")
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
        mock_user_repo.update = AsyncMock(return_value=mock_user)

        user_data = UserUpdateSheme(
            username="new",
            email="new@example.com",
            role="admin",
            team_id=uuid4(),
        )

        result = await user_service.update_user(mock_user_repo, user_id, user_data)

        assert result.username == "new"
        assert result.email == "new@example.com"
        assert result.role == "admin"
        assert mock_user.username == "new"
        assert mock_user.email == "new@example.com"
        assert mock_user.role == "admin"
        mock_user_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_partial(self, user_service, mock_user_repo):
        """Частичное обновление пользователя (только username)."""
        user_id = uuid4()
        mock_user = create_mock_user(user_id, username="old", email="old@example.com")
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
        mock_user_repo.update = AsyncMock(return_value=mock_user)

        user_data = UserUpdateSheme(username="new")

        result = await user_service.update_user(mock_user_repo, user_id, user_data)

        assert result.username == "new"
        assert result.email == "old@example.com"  # Не изменился
        mock_user_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, user_service, mock_user_repo):
        """Обновление несуществующего пользователя."""
        user_id = uuid4()
        mock_user_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(UserNotFound):
            await user_service.update_user(
                mock_user_repo, user_id, UserUpdateSheme(username="new")
            )


class TestUserServiceDeleteUser:
    """Тесты для метода delete_user."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service, mock_user_repo):
        """Успешное удаление пользователя."""
        user_id = uuid4()
        mock_user = create_mock_user(user_id)
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
        mock_user_repo.delete = AsyncMock()

        await user_service.delete_user(mock_user_repo, user_id)

        mock_user_repo.delete.assert_called_once_with(mock_user)

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_service, mock_user_repo):
        """Удаление несуществующего пользователя."""
        user_id = uuid4()
        mock_user_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(UserNotFound):
            await user_service.delete_user(mock_user_repo, user_id)
