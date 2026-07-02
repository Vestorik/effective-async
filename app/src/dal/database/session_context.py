from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, AsyncEngine
from logging import getLogger
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from contextvars import ContextVar
from app.src.dal.repositories import UserRepository
logger = getLogger(__name__)


session_maker_context: ContextVar[async_sessionmaker[AsyncSession] | None]  = ContextVar("session_maker", default=None)
data_base_engine_context: ContextVar[AsyncEngine | None]  = ContextVar("data_base_engine", default=None)

@asynccontextmanager
async def session_transaction(
    session_maker: async_sessionmaker[AsyncSession] | None = None, max_retries: int = 3
) -> AsyncGenerator[AsyncSession]:
    """
    Контекстный менеджер для управления сессией.

    Автоматически:
    - открывает сессию,
    - коммитит при успехе,
    - делает rollback при ошибке,
    - закрывает сессию.

    Аргументы:
        session_maker: Фабрика сессий. Если None — берётся из контекста.

    Возвращает:
        AsyncGenerator[AsyncSession]: Активная сессия.

    Исключения:
        ValueError: Если session_maker не задан.
        Exception: Перехватывается, делается rollback и повторный raise.

    Пример:
        async with session_transaction() as session:
            user = await UserRepository(session).get_by_email("test@example.com")
    """
    session_factory = session_maker or session_maker_context.get()
    
    if session_factory is None:
        raise ValueError("session_factory не должен быть None")
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
            # Убедимся, что сессия закрыта, если ещё не закрыта
            if session and not session.is_closed:  # ty:ignore[unresolved-attribute] \\ Object of type `AsyncSession & ~AlwaysFalsy` exist attribute `is_closed`
                await session.close()

            
def get_engine(engine: AsyncEngine | None = None) -> AsyncEngine:
    """
    Возвращает экземпляр асинхронного движка SQLAlchemy.

    Позволяет переопределить движок (например, для тестов), но по умолчанию возвращает data_base_engine_context.

    Аргументы:
        engine (AsyncEngine | None): Опциональный движок. Если None — возвращается data_base_engine_context.

    Возвращает:
        AsyncEngine: Экземпляр асинхронного движка базы данных.

    Пример:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)           
    """

    result = engine or data_base_engine_context.get()
    if result is None:
        raise ValueError("engine не должен быть None")
    return result

def update_db_context(engine: AsyncEngine | None, session_maker: async_sessionmaker[AsyncSession] | None) -> None:
    """
    Обновляет контекстные переменные для работы с базой данных.

    Аргументы:
        engine (AsyncEngine): Асинхронный движок SQLAlchemy.
        session_maker (async_sessionmaker[AsyncSession]): Фабрика сессий.
    """
    data_base_engine_context.set(engine)
    session_maker_context.set(session_maker)
    
class UnitOfWork:
    """
    Единица работы (Unit of Work) — паттерн DDD для инъекции репозиториев.

    Предоставляет доступ к репозиториям через единую сессию.
    Не управляет транзакцией — предполагается, что сессия управляется внешним кодом
    (например, через session_transaction).

    Атрибуты:
        session (AsyncSession): Активная сессия (передаётся или создаётся).
        users (UserRepository): Репозиторий пользователей.
        profiles (ProfileRepository): Репозиторий профилей.
        skills (SkillRepository): Репозиторий навыков.
        tours (TourRepository): Репозиторий туров.
        bookings (BookingRepository): Репозиторий бронирований.
        business_contexts (BusinesContextRepository): Репозиторий бизнес-контекстов.
        
    Внимание: НЕ вызывайте session.commit() вручную внутри этого блока.
    Коммит будет выполнен автоматически при успешном выходе.
    В случае ошибки — произойдёт rollback.
    """

    def __init__(
        self,
        session_maker: Optional[async_sessionmaker[AsyncSession]] = None,
        session: Optional[AsyncSession] = None,
    ):
        """
        Инициализирует UnitOfWork.

        Можно передать либо session_maker (для создания сессии),
        либо уже активную сессию (например, из session_transaction).

        Аргументы:
            session_maker: Фабрика сессий. Используется, если session не передана.
            session: Уже открытая сессия (например, из внешнего контекста).
        """
        if session is not None:
            self.session = session
        else:
            sm = session_maker or session_maker_context.get()
            if sm is None:
                raise ValueError("session_maker не задан ни в аргументах, ни в контексте")
            self.session = sm()

        self.users: UserRepository = UserRepository(self.session)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Управление сессией — вне ответственности UnitOfWork
        # Пусть внешний код (например, session_transaction) решает, что делать
        pass
    

class DataBaseManager:
    """
    Класс для управления доступом к данным.
    Реализует собой промежуточный слой между обработчиками, кэшом и базой данных.
    Пытается получить данные из кэша, иначе из базы данных.
    
    
    
    """
    session_maker: async_sessionmaker | None = None
    data_base_engine: AsyncEngine | None = None