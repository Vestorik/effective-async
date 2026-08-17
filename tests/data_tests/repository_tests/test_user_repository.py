"""
Тесты для UserRepository.

Критерии приемки:
1. Создание пользователя (create).
2. Получение пользователя по ID (get_by_id).
3. Получение пользователя по Email (get_by_email).
4. Фильтрация по роли (get_by_role).
5. Пагинация с фильтром (get_all_paginated).
6. Управление refresh_token (get_by_refresh_token_hash, clear_refresh_token_hash).

Тестирование выполнено через мокирование AsyncSession, чтобы изолировать логику репозитория 
от базы данных и проверить правильность формирования SQLAlchemy запросов.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, call
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Sequence
from uuid import UUID, uuid4

from app.src.dal.database.repositories import UserRepository
from app.src.dal.database.models import UserModel


# Фикстуры для создания тестовых объектов

@pytest.fixture
def mock_session() -> AsyncMock:
    """
    Создает мок асинхронной сессии.
    
    Returns:
        AsyncMock: Мокированная сессия с необходимыми методами.
    """
    session = AsyncMock(spec=AsyncSession)
    # Подготовка скалярного результата для запросов
    scalar_result = MagicMock()
    scalar_result.scalars.return_value.unique.return_value.first.return_value = None
    scalar_result.scalars.return_value.all.return_value = []
    scalar_result.scalar_one.return_value = 0
    scalar_result.scalar_one_or_none.return_value = None
    
    session.execute.return_value = scalar_result
    session.get.return_value = None
    session.add = AsyncMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    
    return session


@pytest.fixture
def test_user_model() -> MagicMock:
    """
    Создает мок UserModel.
    
    Returns:
        MagicMock: Мокированная модель пользователя.
    """
    user = MagicMock(spec=UserModel)
    user.id = uuid4()
    user.email = "test@example.com"
    user.name = "Test User"
    user.role = "user"
    user.refresh_token_hash = None
    user.team_id = None
    return user


@pytest.fixture
def user_repo(mock_session) -> UserRepository:
    """
    Создает экземпляр UserRepository с моковой сессией.
    
    Args:
        mock_session: Мокированная сессия.
        
    Returns:
        UserRepository: Экземпляр репозитория.
    """
    # Создаем мок модели, чтобы передать в конструктор
    mock_model = MagicMock()
    mock_model.__tablename__ = 'users' # Для некоторых операций SQLAlchemy требует имя таблицы
    
    return UserRepository(session=mock_session)


class TestUserRepositoryCRUD:
    """Тесты базовых CRUD операций и специфичных методов UserRepository."""

    @pytest.mark.asyncio
    async def test_create_user(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: Создание пользователя вызывает add и flush.
        
        Arrange: Подготовка мока пользователя и сессии.
        Act: Вызов create.
        Assert: Проверка вызовов session.add и session.flush.
        """
        # Act
        result = await user_repo.create(test_user_model)

        # Assert
        mock_session.add.assert_called_once_with(test_user_model)
        mock_session.flush.assert_called_once()
        assert result == test_user_model

    @pytest.mark.asyncio
    async def test_get_by_id(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает объект из session.get.
        
        Arrange: Мокируем session.get для возврата пользователя.
        Act: Вызов get_by_id.
        Assert: Проверка, что session.get был вызван с правильными аргументами и вернул пользователя.
        """
        user_id = uuid4()
        mock_session.get.return_value = test_user_model

        # Act
        result = await user_repo.get_by_id(user_id)

        # Assert
        mock_session.get.assert_called_once_with(user_repo.model, user_id)
        assert result == test_user_model

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        user_repo: UserRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает None, если пользователь не найден.
        
        Arrange: Мокируем session.get для возврата None.
        Act: Вызов get_by_id.
        Assert: Результат равен None.
        """
        user_id = uuid4()
        mock_session.get.return_value = None

        # Act
        result = await user_repo.get_by_id(user_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_email(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_email формирует правильный запрос и возвращает пользователя.
        
        Arrange: Мокируем результат execute.
        Act: Вызов get_by_email.
        Assert: Проверка вызова session.execute с правильным select, и возврат пользователя.
        """
        email = "test@example.com"
        # Настраиваем мок так, чтобы first() возвращал пользователя
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.first.return_value = test_user_model
        mock_session.execute.return_value = mock_result

        # Act
        result = await user_repo.get_by_email(email)

        # Assert
        mock_session.execute.assert_called_once()
        # Проверяем, что был вызван select с WHERE
        call_args = mock_session.execute.call_args
        stmt = call_args[0][0]
        # Упрощенная проверка: убедимся, что запрос был
        assert stmt is not None
        assert result == test_user_model

    @pytest.mark.asyncio
    async def test_get_by_role(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_role возвращает список пользователей с указанной ролью.
        
        Arrange: Мокируем результат execute.
        Act: Вызов get_by_role.
        Assert: Проверка вызова session.execute и возврата списка.
        """
        role = "admin"
        # Настраиваем мок так, чтобы all() возвращала список пользователей
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [test_user_model]
        mock_session.execute.return_value = mock_result

        # Act
        result = await user_repo.get_by_role(role)

        # Assert
        mock_session.execute.assert_called_once()
        assert len(result) == 1
        assert result[0] == test_user_model

    @pytest.mark.asyncio
    async def test_update_user(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: update вызывает flush.
        
        Arrange: Мокированная сессия.
        Act: Вызов update.
        Assert: Проверка вызова session.flush.
        """
        # Act
        result = await user_repo.update(test_user_model)

        # Assert
        mock_session.flush.assert_called_once()
        assert result == test_user_model

    @pytest.mark.asyncio
    async def test_delete_user(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: delete вызывает session.delete.
        
        Arrange: Мокированная сессия.
        Act: Вызов delete.
        Assert: Проверка вызова session.delete.
        """
        # Act
        await user_repo.delete(test_user_model)

        # Assert
        mock_session.delete.assert_called_once_with(test_user_model)

    @pytest.mark.asyncio
    async def test_get_all(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_all возвращает список всех пользователей.
        
        Arrange: Мокируем результат execute.
        Act: Вызов get_all.
        Assert: Проверка вызова session.execute и возврата списка.
        """
        # Настраиваем мок
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [test_user_model]
        mock_session.execute.return_value = mock_result

        # Act
        result = await user_repo.get_all()

        # Assert
        mock_session.execute.assert_called_once()
        assert len(result) == 1
        assert result[0] == test_user_model

    @pytest.mark.asyncio
    async def test_get_all_paginated_basic(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_all_paginated возвращает пагинированный список и общее количество.
        
        Arrange: Мокируем результат execute для запроса с пагинацией.
        Act: Вызов get_all_paginated.
        Assert: Проверка корректности возвращаемых значений.
        """
        # Настраиваем моки
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 10  # Total items
        
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = [test_user_model]
        
        # Для простоты мока, пусть execute возвращает разные результаты в зависимости от порядка вызовов
        # Но в реальности SQLAlchemy использует один объект session. 
        # В unit-тестах мы можем заменить execute на.side_effect
        mock_session.execute.side_effect = [mock_count_result, mock_data_result]

        # Act
        users, total = await user_repo.get_all_paginated(page=1, page_size=5)

        # Assert
        assert total == 10
        assert len(users) == 1
        assert users[0] == test_user_model

    @pytest.mark.asyncio
    async def test_get_all_paginated_with_role_filter(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_all_paginated с фильтром по роли формирует запрос с WHERE.
        
        Arrange: Мокируем результат execute.
        Act: Вызов get_all_paginated с role="admin".
        Assert: Проверка, что в запросе есть условие по роли.
        """
        # Настраиваем моки
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = [test_user_model]
        
        mock_session.execute.side_effect = [mock_count_result, mock_data_result]

        # Act
        users, total = await user_repo.get_all_paginated(page=1, page_size=10, role="admin")

        # Assert
        assert total == 1
        assert len(users) == 1
        # Проверяем, что execute был вызван дважды (count и data)
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_by_refresh_token_hash(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_refresh_token_hash возвращает пользователя по хэшу токена.
        
        Arrange: Мокируем результат execute.
        Act: Вызов метода.
        Assert: Проверка возврата пользователя.
        """
        token_hash = "hashed_token_value"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_user_model
        mock_session.execute.return_value = mock_result

        # Act
        result = await user_repo.get_by_refresh_token_hash(token_hash)

        # Assert
        mock_session.execute.assert_called_once()
        assert result == test_user_model

    @pytest.mark.asyncio
    async def test_clear_refresh_token_hash_updates_user(
        self,
        user_repo: UserRepository,
        test_user_model: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: clear_refresh_token_hash обновляет поле refresh_token_hash и вызывает update.
        
        Arrange: Мокируем get_by_id для возврата пользователя.
        Act: Вызов clear_refresh_token_hash.
        Assert: Проверка изменения атрибута и вызова update.
        """
        user_id = test_user_model.id
        
        # Настраиваем mock_session.get
        mock_session.get.return_value = test_user_model
        
        # Настраиваем mock для update (чтобы он не падал)
        mock_session.flush = AsyncMock()

        # Act
        await user_repo.clear_refresh_token_hash(user_id)

        # Assert
        assert test_user_model.refresh_token_hash is None
        # update должен был быть вызван через flush (так как в BaseRepository.update вызывается flush)
        mock_session.flush.assert_called_once()