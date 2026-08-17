"""Тесты модуля кэширования cache_manager.py."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import timedelta

from app.src.dal.cache.cache_manager import (
    CacheManager,
    RedisConfig,
    create_cache_manager_from_config,
    CachedRepositoryProxy,
)


class TestRedisConfig:
    """Тесты конфигурации Redis."""

    def test_redis_config_default_values(self):
        """Тест конфигурации с дефолтными значениями."""
        config = RedisConfig(host="localhost", port=6379, db=0)
        
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.ssl is False

    def test_redis_config_connection_url_without_password(self):
        """Тест генерации URL без пароля."""
        config = RedisConfig(host="localhost", port=6379, db=0)
        
        assert config.connection_url == "redis://localhost:6379/0"



class TestCacheManager:
    """Тесты CacheManager."""

    @pytest.fixture
    def mock_redis(self):
        """Мок-объект Redis."""
        with patch("app.src.dal.cache.cache_manager.Redis") as mock_redis_class:
            mock_instance = AsyncMock()
            mock_redis_class.from_url.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def cache_manager(self, mock_redis):
        """Создаёт CacheManager с мок-Redis."""
        return CacheManager(mock_redis, default_ttl=timedelta(minutes=5))

    @pytest.mark.asyncio
    async def test_get_success(self, cache_manager, mock_redis):
        """Тест успешного получения значения из кэша."""
        mock_redis.get = AsyncMock(return_value=b"cached_value")
        
        result = await cache_manager.get("test_key")
        
        assert result == "cached_value"

    @pytest.mark.asyncio
    async def test_get_not_found(self, cache_manager, mock_redis):
        """Тест получения несуществующего ключа."""
        mock_redis.get = AsyncMock(return_value=None)
        
        result = await cache_manager.get("nonexistent_key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_connection_error(self, cache_manager, mock_redis, caplog):
        """Тест обработки ошибки подключения при get."""
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis connection failed"))
        
        result = await cache_manager.get("test_key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_setex_success(self, cache_manager, mock_redis):
        """Тест успешной записи в кэш."""
        await cache_manager.setex("test_key", timedelta(minutes=10), "value")
        
        mock_redis.setex.assert_called_once_with("test_key", 600, "value")

    @pytest.mark.asyncio
    async def test_setex_invalid_ttl(self, cache_manager, mock_redis):
        """Тест записи с недопустимым TTL."""
        with pytest.raises(ValueError, match="TTL должен быть положительным"):
            await cache_manager.setex("test_key", timedelta(seconds=-1), "value")

    @pytest.mark.asyncio
    async def test_setex_connection_error(self, cache_manager, mock_redis, caplog):
        """Тест обработки ошибки подключения при setex."""
        mock_redis.setex = AsyncMock(side_effect=ConnectionError("Redis connection failed"))
        
        await cache_manager.setex("test_key", timedelta(minutes=5), "value")
        
        # Логирование происходит, но исключение не всплывает

    @pytest.mark.asyncio
    async def test_delete_success(self, cache_manager, mock_redis):
        """Тест успешного удаления ключа."""
        mock_redis.delete = AsyncMock()
        
        await cache_manager.delete("test_key")
        
        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_connection_error(self, cache_manager, mock_redis, caplog):
        """Тест обработки ошибки подключения при delete."""
        mock_redis.delete = AsyncMock(side_effect=ConnectionError("Redis connection failed"))
        
        await cache_manager.delete("test_key")
        
        # Логирование происходит, но исключение не всплывает

    @pytest.mark.asyncio
    async def test_clear_pattern_success(self, cache_manager, mock_redis):
        """Тест очистки по шаблону."""
        mock_redis.keys = AsyncMock(return_value=["key1", "key2", "key3"])
        mock_redis.delete = AsyncMock(return_value=3)
        
        result = await cache_manager.clear_pattern("prefix:*")
        
        assert result == 3

    @pytest.mark.asyncio
    async def test_clear_pattern_no_keys(self, cache_manager, mock_redis):
        """Тест очистки когда ключей нет."""
        mock_redis.keys = AsyncMock(return_value=[])
        
        result = await cache_manager.clear_pattern("prefix:*")
        
        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_pattern_connection_error(self, cache_manager, mock_redis, caplog):
        """Тест обработки ошибки подключения при clear_pattern."""
        mock_redis.keys = AsyncMock(side_effect=ConnectionError("Redis connection failed"))
        
        result = await cache_manager.clear_pattern("prefix:*")
        
        assert result == 0


class TestCreateCacheManagerFromConfig:
    """Тесты функции create_cache_manager_from_config."""

    @patch("app.src.dal.cache.cache_manager.Redis")
    def test_create_cache_manager_with_default_config(self, mock_redis_class):
        """Тест создания CacheManager с дефолтной конфигурацией."""
        mock_redis_instance = MagicMock()
        mock_redis_class.from_url.return_value = mock_redis_instance
        
        cache = create_cache_manager_from_config()
        
        assert isinstance(cache, CacheManager)
        assert cache.redis == mock_redis_instance
        assert cache.default_ttl == timedelta(minutes=5)

    @patch("app.src.dal.cache.cache_manager.Redis")
    def test_create_cache_manager_with_custom_config(self, mock_redis_class):
        """Тест создания CacheManager с кастомной конфигурацией."""
        mock_redis_instance = MagicMock()
        mock_redis_class.from_url.return_value = mock_redis_instance
        
        config = RedisConfig(host="redis.local", port=6380, db=1, password="secret")
        cache = create_cache_manager_from_config(config, ttl=timedelta(minutes=10))
        
        assert cache.default_ttl == timedelta(minutes=10)
        mock_redis_class.from_url.assert_called_once()


class TestCachedRepositoryProxy:
    """Тесты CachedRepositoryProxy."""

    @pytest.fixture
    def mock_repository(self):
        """Мок-объект репозитория."""
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value={"id": "123", "name": "Test"})
        repo.get_all = AsyncMock(return_value=[{"id": "1", "name": "A"}])
        repo.create = AsyncMock(return_value={"id": "456", "name": "New"})
        return repo

    @pytest.fixture
    def mock_cache(self):
        """Мок-объект CacheManager."""
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.setex = AsyncMock()
        cache.delete = AsyncMock()
        return cache

    @pytest.fixture
    def cached_proxy(self, mock_repository, mock_cache):
        """Создаёт CachedRepositoryProxy."""
        return CachedRepositoryProxy(
            repository_obj=mock_repository,
            cache_manager=mock_cache,
            key_prefix="users",
            time_segment=timedelta(minutes=5),
        )

    @pytest.mark.asyncio
    async def test_get_by_id_cache_miss(self, cached_proxy, mock_cache):
        """Тест get_by_id при промахе кэша."""
        mock_cache.get = AsyncMock(return_value=None)
        
        result = await cached_proxy.get_by_id("123")
        
        assert result == {"id": "123", "name": "Test"}

    @pytest.mark.asyncio
    async def test_get_by_id_cache_hit(self, cached_proxy, mock_cache):
        """Тест get_by_id при попадании в кэш."""
        mock_cache.get = AsyncMock(return_value="cached_value")
        
        result = await cached_proxy.get_by_id("123")
        
        assert result == "cached_value"
        mock_cache.setex.assert_not_called()


    @pytest.mark.asyncio
    async def test_get_all_paginated(self, cached_proxy, mock_cache):
        """Тест get_all_paginated с кэшированием."""
        mock_cache.get = AsyncMock(return_value=None)
        mock_repository = cached_proxy._CachedRepositoryProxy__repository_obj
        mock_repository.get_all_paginated = AsyncMock(return_value=([], 0))
        
        result = await cached_proxy.get_all_paginated(page=1, page_size=10)
        
        assert result == ([], 0)
