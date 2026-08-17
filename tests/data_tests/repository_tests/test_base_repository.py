# tests/data_tests/test_repository/test_base_repository.py

"""
Тесты для BaseRepository.

Критерии приемки:
1. create: вызывает add и flush, возвращает объект.
2. update: вызывает flush, возвращает объект.
3. delete: вызывает delete сессии.
4. get_all: возвращает все объекты.
5. get_all_paginated: возвращает пагинированные данные и общее количество.
6. get_all_paginated_by_stmt: возвращает пагинированные данные для кастомного запроса.

Тестирование выполнено через мокирование AsyncSession.
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession

from app.src.dal.database.repositories import BaseRepository, ModelType

# Фикстуры


@pytest.fixture
def mock_session() -> AsyncMock:
    """
    Создает мок асинхронной сессии.
    """
    session = AsyncMock(spec=AsyncSession)
    
    # Подготовка скалярного результата для запросов
    scalar_result = MagicMock()
    scalar_result.scalars.return_value.all.return_value = []
    scalar_result.scalar_one.return_value = 0
    scalar_result.unique.return_value = scalar_result
    
    session.execute.return_value = scalar_result
    session.add = AsyncMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.get = AsyncMock()
    
    return session


# Создаем пустую модель, чтобы использовать её как spec, а не как мок
class TestModel(DeclarativeBase):
    """Временная модель для тестов."""
    __abstract__ = True

@pytest.fixture
def mock_model() -> type:
    """
    Создает класс модели для тестов.
    """
    return TestModel


@pytest.fixture
def base_repo(mock_session, mock_model) -> BaseRepository:
    """
    Создает экземпляр репозитория для тестирования.
    """
    class TestRepository(BaseRepository[TestModel]):
        async def get_by_id(self, obj_id: UUID) -> TestModel | None:
            return None 

    return TestRepository(session=mock_session, model=mock_model)


@pytest.fixture
def test_instance() -> MagicMock:
    """
    Создает мок экземпляра модели (сущности).
    Используем MagicMock напрямую, так как spec класса не подходит для динамического мока данных.
    """
    instance = MagicMock()
    instance.id = uuid4()
    return instance


class TestBaseRepositoryCRUD:
    """Тесты базовых CRUD операций."""

    @pytest.mark.asyncio
    async def test_create_calls_add_and_flush(
        self,
        base_repo: BaseRepository,
        test_instance: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: create вызывает add для нового объекта и flush.
        
        Arrange: Подготовка мока объекта.
        Act: Вызов create.
        Assert: Проверка вызовов session.add и session.flush.
        """
        # Act
        result = await base_repo.create(test_instance)

        # Assert
        mock_session.add.assert_called_once_with(test_instance)
        mock_session.flush.assert_called_once()
        assert result == test_instance

    @pytest.mark.asyncio
    async def test_update_calls_flush(
        self,
        base_repo: BaseRepository,
        test_instance: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: update вызывает flush для обновления существующего объекта.
        
        Arrange: Подготовка мока объекта.
        Act: Вызов update.
        Assert: Проверка вызова session.flush.
        """
        # Act
        result = await base_repo.update(test_instance)

        # Assert
        # Примечание: В текущей реализации BaseRepository.update не вызывает add,
        # предполагая, что объект уже находится в сессии (dirty state).
        mock_session.flush.assert_called_once()
        assert result == test_instance

    @pytest.mark.asyncio
    async def test_delete_calls_session_delete(
        self,
        base_repo: BaseRepository,
        test_instance: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: delete вызывает session.delete.
        
        Arrange: Подготовка мока объекта.
        Act: Вызов delete.
        Assert: Проверка вызова session.delete с объектом.
        """
        # Act
        await base_repo.delete(test_instance)

        # Assert
        mock_session.delete.assert_called_once_with(test_instance)

