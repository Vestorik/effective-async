"""
Модуль управления сессиями и транзакциями для асинхронной работы с базой данных через SQLAlchemy.

Содержит реализацию паттернов:
- Unit of Work (DDD) — для управления транзакциями через единую сессию и набор репозиториев.
- Retry with Fresh Session — для автоматических повторов при временных ошибках (например, потерянное соединение с БД).

Ключевые компоненты:
- `session_transaction`: контекстный менеджер с встроенной стратегией повтора (tenacity) и логированием.
- `UnitOfWork`: реализация паттерна Unit of Work с автоматическим управлением commit/rollback.
- `DataBaseManager`: централизованный хостинг зависимостей (движок + фабрика сессий) для создания UnitOfWork.

Использование:
- Для фоновых задач, где допустимо повторение операции с новой сессией — используйте `session_transaction`.
- Для стандартной серверной логики (HTTP-запросы, сервисы) — используйте `UnitOfWork`.
- `DataBaseManager` выступает как точка инъекции зависимостей и фасад для удобного создания UoW.

Типы обрабатываемых ошибок:
- `sqlalchemy.exc.OperationalError` — временные ошибки БД (переполнение пула, timeout), при которых повтор возможен.

Архитектурные принципы:
- Чистая архитектура: DAL-слой изолирует ORM и инфраструктуру.
- Dependency Injection: `session_maker` и `engine` внедряются извне.
- Single Responsibility: каждый компонент отвечает за одну стратегию управления транзакциями.
- Explicit over Implicit: commit/rollback явны в поведении, логирование — безопасное (без утечек данных).


Примеры:
1. Сервисный слой (FastAPI endpoint):
   ```python
   async def get_user(user_id: UUID, db_manager: DataBaseManager):
       async with db_manager.uof() as uow:
           user = await uow.users.get_by_id(user_id)
           return UserResponse.from_orm(user)



2. Фоновая задача с retry:
async def daily_cleanup(db_session_maker: async_sessionmaker[AsyncSession]):
    async with session_transaction(db_session_maker, max_retries=3) as session:
        expired = await SomeRepository(session).get_expired()
        for item in expired:
            await session.delete(item)
        await session.commit()



3.Обработка ошибок:
async def process_user_event(db_session_maker: async_sessionmaker[AsyncSession], user_id: UUID):
    try:
        async with session_transaction(db_session_maker) as session:
            user = await UserRepository(session).get_by_id(user_id)
            # ... обработка ...
            await session.commit()
    except OperationalError as ex:
        logger.error("Не удалось обработать событие для пользователя %s: %s", user_id, ex)
        raise

"""

from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, AsyncEngine
from logging import getLogger
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from app.src.dal.database.repositories import (
    UserRepository,
    TeamRepository,
    ProjectRepository,
    TaskRepository,
    TaskExecutorRepository,
    MeetingRepository,
    EventRepository,
)

logger = getLogger(__name__)


@asynccontextmanager
async def session_transaction(
    session_maker: async_sessionmaker[AsyncSession], max_retries: int = 3
) -> AsyncGenerator[AsyncSession]:
    """
    Контекстный менеджер для управления сессией с retry и логированием.


    Поведение:
    - Повторяет транзакцию max_retries раз при OperationalError.
    - При каждом retry создаёт **новую сессию** — данные из предыдущих попыток не видны.
    - commit() и rollback() управляются async_sessionmaker (через async with).
    - Логирует попытки и ошибки без утечки чувствительных данных.

    Использование:
        async with session_transaction(session_maker, max_retries=5) as session:
            user = await UserRepository(session).get_by_email("test@example.com")
            # Если упадёт — tenacity создаст новую сессию и повторит

    Аргументы:
        session_maker (async_sessionmaker[AsyncSession]): Фабрика асинхронных сессий.
        max_retries (int): Максимальное количество повторов (по умолчанию 3).

    Возвращаемое значение:
        AsyncGenerator[AsyncSession]: Асинхронный генератор, выдающий активную сессию.

    Исключения:
        OperationalError: Если все попытки исчерпаны и ошибка повторяется.

    Ограничения и допущения:
        - При каждом retry создаётся новая сессия — данные из предыдущих попыток **не видны**.
        - Подходит только для задач, где допустимо "начать с чистого листа" при ошибке.
        - commit() и rollback() управляются async_sessionmaker, неявно.

    Примеры вызова:
        # 1. Фоновая задача с retry
        async with session_transaction(session_maker, max_retries=5) as session:
            user = await UserRepository(session).get_by_email("test@example.com")
            if user:
                await session.commit()

        # 2. Интеграционная задача (например, отправка email-рассылки)
        async with session_transaction(session_maker, max_retries=3) as session:
            users = await UserRepository(session).get_all()
            for user in users:
                await send_email(user.email)
            # commit() при успехе

        # 3. Планировщик (например, cron-задача)
        # @app.cron("0 0 * * *")  # Пример, не синтаксис FastAPI
        async def daily_report():
            async with session_transaction(session_maker) as session:
                stats = await SomeRepository(session).get_daily_stats()
                await send_report(stats)
    """
    session_factory = session_maker

    # Определяем, какие ошибки стоит повторять
    retry_strategy = AsyncRetrying(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type((OperationalError,)),
        reraise=True,
    )

    attempt = 0
    async for attempt_info in retry_strategy:
        attempt += 1
        if attempt > 1:
            logger.warning("Повторная попытка транзакции (попытка %d)", attempt)

        session = session_factory()

        try:
            yield session
            await session.commit()
            logger.debug("Транзакция успешно завершена (попытка %d)", attempt)
            return  # Успешно — выходим

        except Exception as ex:
            try:
                await session.rollback()
            except Exception as rb_ex:
                logger.error("Ошибка при выполнении rollback: %s", rb_ex, exc_info=True)

            # Логируем только нечувствительные данные
            logger.error(
                "Ошибка транзакции (попытка %d/%d): %s",
                attempt,
                max_retries,
                type(ex).__name__,
                exc_info=True,
            )
            # Позволяем tenacity решить — повторять или нет
            if attempt >= max_retries:
                raise
            else:
                # Закрываем сессию перед повтором
                await session.close()
                raise  # Перехватывается tenacity

        finally:
            await session.close()


class UnitOfWork:
    """
    Unit of Work (DDD) — управляет транзакцией через единую сессию.

    Реализует паттерн Unit of Work (Eric Evans, Martin Fowler):
    - Отслеживает изменения объектов в рамках одной транзакции.
    - Гарантирует, что все изменения будут применены атомарно (commit/rollback).
    - Использует одну сессию для всех репозиториев — гарантирует консистентность.

    Использование:
        async with UnitOfWork(session_maker) as uow:
            user = await uow.users.get_by_id(user_id)
            user.name = "New Name"
            await uow.users.update(user)
            # commit() и rollback() вызываются автоматически при выходе из async with

    Атрибуты:
        session (AsyncSession | None): Общая сессия для всех репозиториев (устанавливается в __aenter__).
        users (UserRepository | None): Репозиторий пользователей (использует self.session).
        teams (TeamRepository | None): Репозиторий команд.
        projects (ProjectRepository | None): Репозиторий проектов.
        tasks (TaskRepository | None): Репозиторий задач.
        task_executors (TaskExecutorRepository | None): Репозиторий исполнителей задач.
        meetings (MeetingRepository | None): Репозиторий встреч.
        events (EventRepository | None): Репозиторий событий.

    Аргументы:
        session_maker (async_sessionmaker[AsyncSession]): Фабрика асинхронных сессий.

    Возвращаемое значение:
        None: Конструктор не возвращает значение.

    Возможные исключения:
        ValueError: Если session_maker равен None (проверка отсутствует, но логика требует явный аргумент).
        OperationalError: При создании сессии (перехватывается в __aexit__).

    Ограничения и допущения:
        - Сессия создаётся при входе в async with, не в __init__.
        - commit() и rollback() управляются async_sessionmaker (через __aexit__).
        - **Не поддерживает retry** — при ошибке транзакция прерывается, данные не коммитятся.
        - Репозитории используют одну сессию — гарантирует изоляцию изменений.
        - Не предназначен для фоновых задач с retry (используйте session_transaction).

    Примеры вызова:
        # 1. Простая транзакция
        async with UnitOfWork(session_maker) as uow:
            user = await uow.users.get_by_id(UUID("123..."))
            user.email = "new@example.com"
            await uow.users.update(user)
            # commit() вызывается автоматически

        # 2. Транзакция с обработкой ошибок
        async with UnitOfWork(session_maker) as uow:
            try:
                user = await uow.users.get_by_id(user_id)
                await uow.users.delete(user)
            except Exception as ex:
                logger.error("Ошибка при удалении: %s", ex)
                raise

        # 3. Использование в сервисе
        class UserService:
            def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
                self.session_maker = session_maker

            async def create_user(self, name: str, email: str):
                async with UnitOfWork(self.session_maker) as uow:
                    user = UserModel(name=name, email=email)
                    await uow.users.create(user)
                    # commit() при выходе из async with
    """
    
    
    def __init__(self, session_maker: async_sessionmaker):
        self._session_maker = session_maker


    async def __aenter__(self) -> "UnitOfWork":
        self.session = self._session_maker()
        self.users = UserRepository(self.session)
        self.teams = TeamRepository(self.session)
        self.projects = ProjectRepository(self.session)
        self.tasks = TaskRepository(self.session)
        self.task_executors = TaskExecutorRepository(self.session)
        self.meetings = MeetingRepository(self.session)
        self.events = EventRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Выход из контекста: commit/rollback и закрытие сессии.

        Аргументы:
            exc_type (type | None): Тип исключения.
            exc_val (BaseException | None): Экземпляр исключения.
            exc_tb (traceback | None): Трассировка исключения.

        Возвращаемое значение:
            None.

        Ограничения и допущения:
            - commit() вызывается, если exc_type is None.
            - rollback() вызывается, если exc_type не None.
            - Сессия закрывается в любом случае.
        """
        if self.session:
            try:
                if exc_type is None:
                    await self.session.commit()
                else:
                    await self.session.rollback()
            finally:
                await self.session.close()


class DataBaseManager:
    """
    Менеджер базы данных, обеспечивающий централизованное управление сессиями и движком SQLAlchemy.

    Класс инкапсулирует инфраструктурные зависимости (движок и фабрику сессий), предоставляя удобный метод
    для получения объекта UnitOfWork — реализации паттерна «Единица работы» (Unit of Work) для асинхронной работы с БД.

    Основные задачи:
    - Хранение ссылок на движок и фабрику сессий, чтобы избежать дублирования конфигурации.
    - Предоставление централизованного способа создания единиц работы для транзакционных операций.

    Атрибуты:
        __session_maker: async_sessionmaker — Фабрика асинхронных сессий SQLAlchemy.
        __data_base_engine: AsyncEngine — Асинхронный движок базы данных для выполнения запросов.

    Методы:
        uof: Получение новой единицы работы (UnitOfWork) на основе фабрики сессий.
    """

    __session_maker: async_sessionmaker
    __data_base_engine: AsyncEngine

    def __init__(self, session_maker: async_sessionmaker, engine: AsyncEngine):
        self.__session_maker: async_sessionmaker = session_maker
        self.__data_base_engine: AsyncEngine = engine
    
    def uow(self) -> UnitOfWork:
        return UnitOfWork(self.__session_maker)

    @property
    def get_engine(self):
        return self.__data_base_engine 