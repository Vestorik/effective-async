from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import timedelta

class CacheManagerInterface(ABC):
    """
    Интерфейс для работы с кэшем (Redis/Memcached).

    Позволяет инъекцию реализации (например, RedisCacheManager).

    Аргументы:
        None

    Возвращает:
        CacheManagerInterface: Экземпляр кэш-сервиса.

    Возможные исключения:
        NotImplementedError: при вызове абстрактного метода без реализации.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Получает значение из кэша по ключу.

        Аргументы:
            key (str): Ключ кэша.

        Возвращает:
            Optional[Any]: Значение или `None`, если ключ не найден.
        """
        raise NotImplementedError

    @abstractmethod
    async def setex(self, key: str, ttl: timedelta, value: Any) -> None:
        """
        Устанавливает значение в кэш с TTL.

        Аргументы:
            key (str): Ключ кэша.
            ttl (timedelta): Время жизни кэша.
            value (Any): Значение для сохранения.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Удаляет ключ из кэша.

        Аргументы:
            key (str): Ключ кэша.
        """
        raise NotImplementedError

    @abstractmethod
    async def clear_pattern(self, pattern: str) -> int:
        """
        Удаляет все ключи по шаблону (например, `user:*`).

        Аргументы:
            pattern (str): Шаблон ключей.

        Возвращает:
            int: Количество удалённых ключей.
        """
        raise NotImplementedError
    
from app.src.dal.cache.manager import CacheManagerInterface
from redis.asyncio import Redis
from datetime import timedelta

class RedisCacheManager(CacheManagerInterface):
    """
    Реализация CacheManagerInterface для Redis.

    Аргументы:
        redis_client (Redis): Асинхронный клиент Redis.

    Возвращает:
        RedisCacheManager: Экземпляр для работы с Redis.
    """

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def get(self, key: str) -> Optional[Any]:
        value = await self.redis.get(key)
        return value.decode() if value else None

    async def setex(self, key: str, ttl: timedelta, value: Any) -> None:
        await self.redis.setex(key, int(ttl.total_seconds()), value)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def clear_pattern(self, pattern: str) -> int:
        keys = await self.redis.keys(pattern)
        if keys:
            return await self.redis.delete(*keys)
        return 0