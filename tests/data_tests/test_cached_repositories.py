"""Тесты кэшированных репозиториев cache_manager.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta

from app.src.dal.database.session_manage import DataBaseManager, UnitOfWork
from app.src.dal.cache.cache_manager import (
    CacheManager,
    CachedRepositoryProxy,
    CachedUnitOfWork,
)


class TestCachedRepositoryProxy:
    """Тесты CachedRepositoryProxy."""

    @pytest.fixture
    def mock_repository(self):
        """Мок-объект репозитория."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value={"id": "123", "name": "Test"})
        repo.get_all = AsyncMock(return_value=[{"id": "1", "name": "A"}])
        repo.create = AsyncMock(return_value={"id": "456", "name": "New"})
        return repo

    @pytest.fixture
    def mock_cache(self):
        """Мок-объект CacheManager."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.setex = AsyncMock()
        return cache

    @pytest.fixture
    def cached_proxy(self, mock_repository, mock_cache):
        """Создаёт CachedRepositoryProxy."""
        return CachedRepositoryProxy(
            repository_obj=mock_repository,
            cache_manager=mock_cache,
            key_prefix="tasks",
            time_segment=timedelta(minutes=5),
        )

    @pytest.mark.asyncio
    async def test_get_by_id_cache_miss(self, cached_proxy, mock_cache):
        """Тест get_by_id при промахе кэша."""
        mock_cache.get.return_value = None

        result = await cached_proxy.get_by_id("123")

        assert result == {"id": "123", "name": "Test"}
        mock_cache.get.assert_called()
        call_args = mock_cache.get.call_args
        assert call_args is not None
        
        mock_cache.get.assert_called_once_with("tasks:get_by_id:123") 
        mock_cache.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_cache_hit(self, cached_proxy, mock_cache):
        """Тест get_by_id при попадании в кэш."""
        mock_cache.get.return_value = "cached_value"

        result = await cached_proxy.get_by_id("123")

        assert result == "cached_value"
        mock_cache.get.assert_called_once_with("tasks:get_by_id:123")
        mock_cache.setex.assert_not_called()



    @pytest.mark.asyncio
    async def test_get_all_paginated(self, cached_proxy, mock_cache):
        """Тест get_all_paginated с кэшированием."""
        mock_cache.get.return_value = None
        mock_repository = cached_proxy._CachedRepositoryProxy__repository_obj
        mock_repository.get_all_paginated = AsyncMock(return_value=([], 0))

        result = await cached_proxy.get_all_paginated(page=1, page_size=10)

        assert result == ([], 0)
        mock_cache.get.assert_called_once()
        mock_cache.setex.assert_called_once()

    def test_non_callable_attributes(self, mock_repository, mock_cache):
        """Тест атрибутов, которые не являются вызываемыми."""
        mock_repository.some_attr = "value"
        cached_proxy = CachedRepositoryProxy(
            repository_obj=mock_repository,
            cache_manager=mock_cache,
            key_prefix="test",
            time_segment=timedelta(minutes=5),
        )

        assert cached_proxy.some_attr == "value"


class TestCachedUnitOfWork:
    """Тесты CachedUnitOfWork."""

    @pytest.fixture
    def mock_database_manager(self):
        """Мок-объект DataBaseManager."""
        db_manager = MagicMock(spec=DataBaseManager)
        uow = MagicMock(spec=UnitOfWork)
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock()
        uow.users = MagicMock()
        uow.teams = MagicMock()
        uow.projects = MagicMock()
        uow.tasks = MagicMock()
        uow.task_executors = MagicMock()
        uow.meetings = MagicMock()
        uow.events = MagicMock()
        uow.comments = MagicMock()
        db_manager.uow = MagicMock(return_value=uow)
        return db_manager

    @pytest.fixture
    def mock_cache_manager(self):
        """Мок-объект CacheManager."""
        return MagicMock(spec=CacheManager)

    @pytest.fixture
    def cached_uow(self, mock_database_manager, mock_cache_manager):
        """Создаёт CachedUnitOfWork."""
        return CachedUnitOfWork(
            database=mock_database_manager,
            cache_manager=mock_cache_manager,
            time_segment=timedelta(minutes=10),
        )

    @pytest.mark.asyncio
    async def test_context_manager_enter(self, cached_uow, mock_database_manager):
        """Тест входа в контекстный менеджер."""
        async with cached_uow as uow:
            assert uow.users is not None
            assert uow.teams is not None
            assert uow.projects is not None
            assert uow.tasks is not None
            assert uow.task_executors is not None
            assert uow.meetings is not None
            assert uow.events is not None

    @pytest.mark.asyncio
    async def test_context_manager_exit(self, cached_uow, mock_database_manager):
        """Тест выхода из контекстного менеджера."""
        uow_instance = MagicMock()
        uow_instance.__aenter__ = AsyncMock(return_value=uow_instance)
        uow_instance.__aexit__ = AsyncMock()
        mock_database_manager.uow.return_value = uow_instance

        async with cached_uow:
            pass

        uow_instance.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uow_exit_with_exception(self, cached_uow, mock_database_manager):
        """Тест выхода из контекста с исключением."""
        uow_instance = MagicMock()
        uow_instance.__aenter__ = AsyncMock(return_value=uow_instance)
        uow_instance.__aexit__ = AsyncMock()
        mock_database_manager.uow.return_value = uow_instance

        try:
            async with cached_uow:
                raise ValueError("Test error")
        except ValueError:
            pass

        uow_instance.__aexit__.assert_awaited_once()
