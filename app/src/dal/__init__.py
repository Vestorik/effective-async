"""
DAL (Data Access Layer) — модуль для работы с базой данных и кэшем.

Экспортируемые компоненты:
- DataManager: единый интерфейс для работы с данными (кэш + БД).
- CacheManagerInterface: интерфейс для кэш-сервисов (Redis, Memcached).
- RedisCacheManager: реализация CacheManagerInterface для Redis.
- UnitOfWork: паттерн Unit of Work для транзакций с БД.
- repository: модуль с репозиториями (UserRepository, TeamRepository и т.д.).

Зависимости:
- sqlalchemy (asyncpg, aiosqlite)
- redis (для RedisCacheManager)
- pydantic (для валидации)

Примеры:
    # 1. Простой read-запрос
    dm = DataManager(cache_manager, session_maker)
    user = await dm.users.get_by_id(user_id)

    # 2. Транзакция
    async with DataManager(cache_manager, session_maker) as dm:
        user = await dm.users.get_by_id(user_id)
        await dm.uow.users.update(user)
"""

__all__ = ["DataManager", "CacheManagerInterface", "RedisCacheManager", "UnitOfWork"]