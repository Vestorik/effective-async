from datetime import timedelta
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine, AsyncSession
from app.src.dal.cache.cache_manager import (
    create_cache_manager_from_config,
    CacheManager,
    CachedUnitOfWork,
)
from app.src.dal.database.session_manage import DataBaseManager, UnitOfWork
from app.src.dal.database.engine import start_engine
from logging import getLogger

logger = getLogger(__name__)


class DataManager:
    """
    Центральный интерфейс - контекстный менеджер для работы с данными.

    Автоматически:
    - проверяет кэш перед запросом к БД,
    - сохраняет результат в кэш после успешного запроса,
    - управляет транзакциями через Unit of Work.

    реализует два интерфейса:
     - manager() запросы к бд
     - manager.cache(timedelta(10) запросы к кэшу, если промах - то обращение к базе

    пример:
    async with manager() as uow:
        await uow.events.delete(1)
        await uow.users.get_all_paginated()

    async with manager.cache(timedelta(10)) as cuow:
        await cuow.events.delete(10)
        await cuow.users.get_all_paginated()

    Использует паттерн Unit of Work в объектах.
    """

    def __init__(
        self,
        session_engine: AsyncEngine,
        session_maker: async_sessionmaker[AsyncSession],
    ):
        self.__cache: CacheManager = create_cache_manager_from_config()
        self.__database = DataBaseManager(session_maker, session_engine)

    def __call__(self) -> UnitOfWork:
        return self.__database.uow()

    def cache(self, time_sigment: timedelta) -> CachedUnitOfWork:
        return CachedUnitOfWork(self.__database, self.__cache, time_sigment)

    @property
    def database_manager(self) -> DataBaseManager:
        return self.__database

    async def close(self) -> None:
        """
        Асинхронно закрывает движок базы данных и освобождает все ресурсы пула соединений.

        Вызывает:
        - engine.dispose() — корректное закрытие пула, уничтожение всех соединений.
        - Логирование без утечки чувствительных данных (URL не логируется, только тип БД).

        Повторный вызов безопасен: повторный `engine.dispose()` не вызывает ошибок.

        Возможные исключения:
            SQLAlchemyError: если возникает ошибка при закрытии движка (редко, но возможна при
            нештатных ситуациях в драйвере).
        """
        try:
            engine = self.__database.get_engine()

            if engine:
                await engine.dispose()
                logger.info("Движок БД корректно закрыт (dispose)")
            else:
                logger.debug("Движок БД уже был закрыт или не был инициализирован")
        except Exception as ex:
            logger.warning(
                "Ошибка при закрытии движка БД: %s", type(ex).__name__, exc_info=True
            )


async def get_data_manager() -> DataManager:
    engine = await start_engine()
    manager = DataManager(*engine)
    return manager
