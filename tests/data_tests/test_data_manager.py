"""Тесты DataManager main.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta

from app.src.dal.main import DataManager, get_data_manager


class TestDataManager:
    """Тесты DataManager."""

    @pytest.fixture
    def mock_engine(self):
        """Мок-объект AsyncEngine."""
        return AsyncMock()

    @pytest.fixture
    def mock_session_maker(self):
        """Мок-объект async_sessionmaker."""
        return AsyncMock()

    @pytest.fixture
    def data_manager(self, mock_engine, mock_session_maker):
        """Создаёт DataManager с моками."""
        with patch("app.src.dal.main.create_cache_manager_from_config") as mock_cache:
            mock_cache_manager = MagicMock()
            mock_cache.return_value = mock_cache_manager
            
            dm = DataManager(mock_engine, mock_session_maker)
            dm._DataManager__cache = mock_cache_manager
            dm._DataManager__database = MagicMock()
            dm._DataManager__database.uow = MagicMock(return_value=AsyncMock())
            dm._DataManager__database.get_engine = MagicMock(return_value=mock_engine)
            
            return dm

    def test_init(self, mock_engine, mock_session_maker):
        """Тест инициализации DataManager."""
        with patch("app.src.dal.main.create_cache_manager_from_config") as mock_cache:
            mock_cache_manager = MagicMock()
            mock_cache.return_value = mock_cache_manager
            
            dm = DataManager(mock_engine, mock_session_maker)
            
            assert dm._DataManager__session_engine == mock_engine
            assert dm._DataManager__session_maker == mock_session_maker
            assert dm._DataManager__cache is not None

    def test_call_returns_uow(self, data_manager):
        """Тест вызова DataManager как функции."""
        uow = data_manager()
        
        assert uow is not None

    def test_cache_returns_cached_uow(self, data_manager):
        """Тест метода cache()."""
        cached_uow = data_manager.cache(timedelta(minutes=10))
        
        assert cached_uow is not None

    async def test_close_success(self, data_manager, mock_engine):
        """Тест успешного закрытия DataManager."""
        await data_manager.close()
        
        mock_engine.dispose.assert_awaited_once()

    async def test_close_engine_not_exists(self, data_manager):
        """Тест закрытия когда движок уже закрыт."""
        data_manager._DataManager__database.get_engine = MagicMock(return_value=None)
        
        await data_manager.close()
        
        # Не должно вызвать ошибку

    async def test_close_error_handling(self, data_manager, caplog):
        """Тест обработки ошибки при закрытии."""
        data_manager._DataManager__database.get_engine = MagicMock(side_effect=Exception("Test error"))
        
        await data_manager.close()
        
        # Ошибка логируется, но не всплывает


class TestGetDataManager:
    """Тесты функции get_data_manager."""

    @pytest.mark.asyncio
    async def test_get_data_manager(self):
        """Тест создания DataManager."""
        with patch("app.src.dal.main.start_engine") as mock_start_engine, \
             patch("app.src.dal.main.DataManager") as mock_dm_class:
            
            mock_engine = AsyncMock()
            mock_session_maker = AsyncMock()
            mock_start_engine.return_value = (mock_engine, mock_session_maker)
            
            mock_dm_instance = MagicMock()
            mock_dm_class.return_value = mock_dm_instance
            
            result = await get_data_manager()
            
            assert result is not None
            mock_dm_class.assert_called_once()
