"""
Модуль управления асинхронными подключениями к базе данных и инициализации движка SQLAlchemy.

Назначение:
    Предоставляет централизованный механизм инициализации асинхронных подключений к
    PostgreSQL/SQLite с автоматическим fallback-переключением, валидацией конфигурации
    и управлением пулами соединений. Поддерживает продакшен-стандарты: таймауты, pre-ping,
    реконнекционную логику и безопасную кодировку паролей.

Архитектура:
    - PostgresDatabaseConfig: Pydantic-конфигурация PostgreSQL с валидацией и computed-полем connection_url.
    - create_postgre_engine(): Стандартная инициализация AsyncEngine с оптимизированными настройками пула.
    - create_sqlite_engine(): Fallback-инициализация для разработки и тестов.
    - create_session_maker(): Фабрика async_sessionmaker для DI в репозиториях и UoW.
    - start_engine(): Главная точка входа с fallback-логикой PostgreSQL → SQLite.

Ключевые принципы:
    - Fail Fast: Конфигурация валидируется при создании (field_validator/model_validator).
    - Fail Over: Автоматический fallback на SQLite при недоступности PostgreSQL.
    - Security First: quote_plus() для паролей, логирование предупреждений о weak passwords.
    - Production Ready: Настройки пула соединений (pool_size, pre_ping, recycle) в соответствии с рекомендациями SQLAlchemy.
    - Explicit is Better than Implicit: Все параметры задаются явно через переменные окружения.

Конфигурация (переменные окружения с префиксом POSTGRES_):
    - HOST, PORT, USER, PASSWORD, DB — обязательные параметры подключения.
    - POOL_SIZE (по умолчанию 10), MAX_OVERFLOW (20), POOL_TIMEOUT (30) — управление пулом.
    - POOL_PRE_PING (True), POOL_RECYCLE (3600) — предотвращение «мертвых» соединений.
    - ECHO (False) — отладочное логирование.

Поддержка SQLite:
    - SQLITE_SUPPORTED — глобальный флаг, разрешающий fallback на SQLite.
    - Файл базы: <project_root>/app/src/dal/database/data/.database.db.
    - Конфигурация: StaticPool + check_same_thread=False для совместимости с async/await.

Инициализация:
    1. Загрузка конфигурации из .env или переменных окружения.
    2. Попытка подключения к PostgreSQL.
    3. При ошибке — проверка флага SQLITE_SUPPORTED → fallback на SQLite.
    4. Выполнение pre-flight check (SELECT 1) для подтверждения готовности.
    5. Создание таблиц (если используются models.Base.metadata.create_all()).
    6. Возврат (engine, session_maker) для DI в репозиториях и UoW.

Типичное использование:
    >>> engine, session_maker = await start_engine()
    >>> async with session_maker() as session:
    ...     result = await session.execute(select(User))

Ограничения:
    - PostgreSQL требует установки драйвера asyncpg.
    - SQLite не подходит для production с высокой нагрузкой (ограничения одновременных записей).
    - Для SQLite требуется Python >= 3.12 (встроенный async/await поддержка aiosqlite).
    - Пароли с спецсимволами автоматически кодируются (quote_plus), что может повлиять на legacy-системы.

Безопасность:
    - Пароль не логируется.
    - Валидация host/user/db_name на пустые значения.
    - Предупреждение при совпадении пароля и логина.
    - Никаких secrets в URL-логах.

Ошибки:
    - ConnectionRefusedError, TimeoutError: при недоступности PostgreSQL/SQLite.
    - ValueError: при валидации конфигурации (пустые поля, некорректный порт).
    - SystemExit(1): при полном отказе подключения к БД (fallback недоступен).

Логирование:
    - INFO: успешное подключение, создание сессий, таблиц.
    - WARNING: fallback на SQLite, ошибки pre-ping, weak passwords.
    - CRITICAL: полная недоступность БД — завершение работы.
"""

import logging
from pathlib import Path
from sys import exit as sysexit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.src.base.config import PostgresDatabaseConfig

# состояние поддержки SQLite 
SQLITE_SUPPORTED = False


logger = logging.getLogger(__name__)


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


def create_postgre_engine(db_config: PostgresDatabaseConfig) -> AsyncEngine:
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

    database_url = db_config.connection_url
    other_config = db_config.model_dump(exclude={"connection_url"})
    
    logger.info("Попытка подключения к базе данных PostgreSQL")
    postgre_engine: AsyncEngine = create_async_engine(database_url, **other_config)
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
    path_database = Path(__file__).resolve().parent / "data" / ".database.db"
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


async def start_engine(database_config: PostgresDatabaseConfig | None = None) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
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



    db_config: PostgresDatabaseConfig = database_config or PostgresDatabaseConfig()
    logger.info("Получение DATABASE_URL из переменных окружения",)
    

    engine: AsyncEngine = create_postgre_engine(db_config)
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





        


