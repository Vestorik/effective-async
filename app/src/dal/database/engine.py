from pathlib import Path
from typing import Tuple
import logging
from sys import exit as sysexit
from os import getenv
from sqlalchemy.pool import StaticPool
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
    create_async_engine,
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# состояние поддержки SQLite 
SQLITE_SUPPORTED = False


def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создаёт и возвращает фабрику асинхронных сессий SQLAlchemy.

    Фабрика сессий используется для создания экземпляров `AsyncSession`,
    которые обеспечивают взаимодействие с базой данных в асинхронном режиме.
    Настройки сессии сконфигурированы для типичного использования в веб-приложениях:
    отложенная фиксация, ручное управление транзакциями и отключение автоматического
    сброса состояния после коммита.

    Аргументы:
        engine (AsyncEngine): Асинхронный движок SQLAlchemy, привязываемый к сессии.
            Должен быть уже настроен и подключён к базе данных.

    Возвращает:
        async_sessionmaker[AsyncSession]: Фабрика для создания асинхронных сессий.

    Пример использования:
        >>> engine = create_async_engine("sqlite+aiosqlite:///example.db")
        >>> session_maker = create_session_maker(engine)
        >>> async with session_maker() as session:
        ...     result = await session.execute(select(User))
    """
    session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    logger.info("Фабрика сессий создана")
    return session_maker


def create_postgre_engine(database_url: str | URL) -> AsyncEngine:
    """Создаёт асинхронный движок SQLAlchemy для подключения к PostgreSQL.

    Функция инициализирует движок с оптимизированными настройками пула соединений,
    предназначенными для стабильной и эффективной работы в асинхронном приложении.
    Используется библиотека `asyncpg` как драйвер.

    Аргументы:
        database_url (str | URL): Строка подключения к базе данных PostgreSQL
            или объект `sqlalchemy.URL`. Должна содержать все необходимые параметры,
            включая имя пользователя, пароль, хост, порт и имя базы данных.

    Возвращает:
        AsyncEngine: Асинхронный движок SQLAlchemy, готовый к использованию
            для создания сессий и выполнения запросов.

    Настройки пула:
        - pool_size: 10 — минимальное количество соединений в пуле.
        - max_overflow: 20 — максимальное количество дополнительных соединений
        при превышении нагрузки.
        - pool_pre_ping: True — проверка соединения перед использованием
        для предотвращения ошибок из-за простроченных подключений.
        - pool_recycle: 3600 — пересоздание соединений каждые 3600 секунд (1 час)
        для предотвращения разрыва соединений на стороне сервера.
        - pool_timeout: 30 — максимальное время ожидания доступного соединения
        из пула (в секундах).
        - echo: False — отключение логирования SQL-запросов (для production).

    Пример строки подключения:
        postgresql+asyncpg://user:password@localhost:5432/dbname

    Пример использования:
        >>> engine = create_postgre_engine("postgresql+asyncpg://user:pass@localhost/db")
        >>> async with engine.begin() as conn:
        ...     await conn.execute(text("SELECT 1"))

    Замечания:
        Убедитесь, что сервер PostgreSQL доступен по указанному адресу
        и что зависимости `asyncpg` и `sqlalchemy[asyncio]` установлены.
    """
    logger.info("Попытка подключения к базе данных PostgreSQL")
    postgre_engine: AsyncEngine = create_async_engine(
        database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,
    )
    return postgre_engine


def create_sqlite_engine() -> AsyncEngine:
    """Создаёт асинхронный движок SQLAlchemy для подключения к базе данных SQLite.

    Используется в качестве резервной или fallback-базы данных при недоступности
    основной базы (например, PostgreSQL). Подходит для разработки и тестирования,
    но не рекомендуется для production-среды из-за ограниченной поддержки
    одновременных записей в асинхронном режиме.

    Возвращает:
        AsyncEngine: Асинхронный движок SQLAlchemy, настроенный для работы с SQLite
        через драйвер `aiosqlite`.

    Особенности конфигурации:
        - База данных создаётся локально в корне проекта под именем `.database.db`.
        - Используется `StaticPool` — пул соединений, который не пересоздаётся,
        что необходимо при использовании асинхронных соединений с SQLite.
        - `connect_args={"check_same_thread": False}` — отключает проверку потока,
        поскольку асинхронное выполнение может происходить в разных потоках.
        - `pool_pre_ping=True` — проверяет соединение перед использованием,
        предотвращая ошибки при простроченных соединениях.
        - `echo=False` — отключено логирование SQL-запросов.

    Пример использования:
        >>> engine = create_sqlite_engine()
        >>> async with engine.begin() as conn:
        ...     await conn.run_sync(Base.metadata.create_all)

    Замечания:
        - Файл базы данных создаётся автоматически при первом подключении.
        - Не используйте этот движок в высоконагруженных или многопользовательских
        production-средах.
        - Рекомендуется включать только как fallback-решение.
    """
    path_to_file = Path(__file__).resolve().parent
    path_database = path_to_file / "data" / ".database.db"
    SQLITE_DATABASE_URL = f"sqlite+aiosqlite:///{path_database}"
    logger.info("Попытка подключения к базе данных Sqlite")
    sqlite_engine: AsyncEngine = create_async_engine(
        SQLITE_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    return sqlite_engine


async def start_engine(data_base_url: str | None= None) -> Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Инициализирует и запускает асинхронный движок базы данных с поддержкой fallback-режима.

    Функция пытается подключиться к основной базе данных (PostgreSQL) по URL из переменной
    окружения `DATA_BASE`. Если переменная не задана или подключение не удалось,
    автоматически переключается на локальную SQLite-базу в качестве резервного варианта.

    В случае полного отказа подключения к любой из баз данных — приложение завершается с кодом 1.

    Возвращает:
        tuple[AsyncEngine, async_sessionmaker[AsyncSession]]: Пара, содержащая:
            - Асинхронный движок SQLAlchemy (PostgreSQL или SQLite).
            - Фабрику сессий для создания экземпляров `AsyncSession`.

    Этапы работы:
        1. Проверка наличия `DATA_BASE` в переменных окружения.
        2. При наличии — попытка подключения к PostgreSQL.
        3. При отсутствии или ошибке — переход на SQLite с проверкой соединения.
        4. Создание всех таблиц в БД, если они ещё не существуют.
        5. Возврат движка и фабрики сессий.

    Внутренние функции:
        test_connection(conn_engine: AsyncEngine) -> bool:
            Выполняет тестовый запрос `SELECT 1` для проверки работоспособности соединения.
            Логирует успех или ошибку.

        check_sqlite() -> AsyncEngine:
            Создаёт движок SQLite и проверяет его доступность.
            При неудаче — завершает работу приложения.

    Логирование:
        - INFO: успешное подключение к БД, создание таблиц.
        - WARNING: отсутствие DATABASE_URL, ошибка подключения к PostgreSQL, fallback на SQLite.
        - CRITICAL: полная недоступность всех БД — завершение работы.

    Пример использования:
        >>> engine, session_maker = await start_engine()
        >>> async with session_maker() as session:
        ...     result = await session.execute(select(User))

    Замечания:
        - Необходимо убедиться, что `DATA_BASE` установлен, если используется PostgreSQL.
        - Файл SQLite создаётся автоматически в корне проекта как `.database.db`.
        - Все модели должны быть импортированы в `database.models.Base`, иначе таблицы не создадутся.
    """
    
    async def test_connection(conn_engine: AsyncEngine) -> bool:
        """Проверяет соединение с базой данных, выполняя тестовый SQL-запрос.

        Аргументы:
            conn_engine (AsyncEngine): Движок SQLAlchemy для проверки.

        Возвращает:
            bool: True, если соединение успешно, иначе False.
        """
        try:
            async with conn_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Подключение к БД успешно")
            return True
        except Exception as e:
            logger.warning("Не удалось подключиться к БД: %s", e)
            return False

    async def check_sqlite() -> AsyncEngine:
        """Создаёт и проверяет подключение к SQLite-базе данных.

        Возвращает:
            AsyncEngine: Работоспособный движок SQLite.

        Если подключение не удалось — логирует критическую ошибку и завершает приложение.
        """
        engine: AsyncEngine = create_sqlite_engine()
        if await test_connection(engine):
            logger.info("Подключение к SQLite успешно")
            return engine
        else:
            logger.critical("Подключение к БД не возможно. Завершение работы")
            sysexit(1)

    DATABASE_URL: str | None = data_base_url or getenv("DATABASE_URL")
    logger.info("Получение DATABASE_URL из переменных окружения: %s", DATABASE_URL)
    if DATABASE_URL is None:
        logger.warning("DATABASE_URL не задан в переменных окружения",)
        if SQLITE_SUPPORTED:
            engine = await check_sqlite()
        else: 
            raise Exception("DATABASE_URL не задан в переменных окружения, поддержка sqlite отключена")
            
    else:
        engine: AsyncEngine = create_postgre_engine(DATABASE_URL)
        if await test_connection(engine):
            logger.info("Подключение к PostgreSQL успешно")
        else:
            logger.warning("PostgreSQL недоступен. Переключение на SQLite.")
            if SQLITE_SUPPORTED:
                engine = await check_sqlite()
            else: 
                raise Exception("PostgreSQL недоступен, поддержка sqlite отключена")

    session_maker: async_sessionmaker[AsyncSession] = create_session_maker(engine)

    return engine, session_maker





        


