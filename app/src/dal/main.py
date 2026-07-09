from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine

from app.src.dal.cache.manager import CacheManagerInterface
from app.src.dal.database.unit_of_work import UnitOfWork
from app.src.dal.database.repositories import (
    UserRepository,
    TeamRepository,
    ProjectRepository,
    TaskRepository,
    TaskExecutorRepository,
    MeetingRepository,
    EventRepository,
)

# --- Constants ---
CACHE_TTL_DEFAULT = timedelta(minutes=5)
CACHE_TTL_SHORT = timedelta(seconds=30)
CACHE_TTL_LONG = timedelta(hours=1)


class _CachedRepositoryProxy:
    """
    Прокси для репозитория с автоматическим кэшированием.

    При вызове метода:
    - если метод "read-only" (get_by_id, get_all, get_by_email, и т.д.) — проверяет кэш.
    - если кэш-промах — вызывает репозиторий, сохраняет результат в кэш.
    - если метод "write" (create, update, delete) — вызывает репозиторий без кэша.

    Аргументы:
        cache (CacheManagerInterface): Кэш-сервис.
        repo_factory (Callable[[], BaseRepository]): Фабрика для создания репозитория.
        ttl (timedelta): TTL по умолчанию для кэша.
    """

    # Список read-only методов (безSideEffects)
    _READ_ONLY_METHODS = {
        "get_by_id",
        "get_all",
        "get_all_paginated",
        "get_all_paginated_by_stmt",
        "get_by_email",
        "get_by_role",
        "get_by_name",
        "get_by_user_id",
        "get_teams_for_project",
        "get_users_for_project",
        "get_by_project_id",
        "get_by_user_id",
        "get_sub_tasks",
        "get_parent_task",
        "get_by_task_and_user",
        "get_executors_for_task",
        "get_tasks_for_user",
    }

    def __init__(
        self,
        cache: CacheManagerInterface,
        repo_factory: Any,
        ttl: timedelta,
    ):
        self._cache = cache
        self._repo_factory = repo_factory
        self._ttl = ttl
        self._repo_instance: Any = None

    def __getattr__(self, name: str) -> Any:
        """
        Перехватывает вызовы методов.

        Если метод read-only — проверяет/сохраняет кэш.
        Если write — вызывает репозиторий напрямую.
        """
        if name.startswith("_"):
            return super().__getattr__(name)

        # Если метод read-only — кэшируем
        if name in self._READ_ONLY_METHODS:
            return self._create_cached_method(name)
        else:
            # Для write-операций — без кэша
            if self._repo_instance is None:
                self._repo_instance = self._repo_factory()
            return getattr(self._repo_instance, name)

    def _create_cached_method(self, method_name: str):
        """
        Создаёт обёртку для read-only метода с кэшированием.
        """

        async def cached_call(*args, **kwargs):
            # Генерируем ключ кэша: "UserRepository.get_by_id:123"
            cache_key = self._generate_cache_key(method_name, args, kwargs)

            # 1. Проверка кэша
            cached = await self._cache.get(cache_key)
            if cached:
                return cached

            # 2. Запрос к БД
            if self._repo_instance is None:
                self._repo_instance = self._repo_factory()

            # Вызов репозитория
            method = getattr(self._repo_instance, method_name)
            result = await method(*args, **kwargs)

            # 3. Сохранение в кэш (если результат не None)
            if result is not None:
                await self._cache.setex(cache_key, self._ttl, result)

            return result

        return cached_call

    def _generate_cache_key(self, method_name: str, args: tuple, kwargs: dict) -> str:
        """
        Генерирует уникальный ключ кэша на основе:
        - имени репозитория,
        - имени метода,
        - аргументов (ID, фильтры и т.д.).

        Аргументы:
            method_name (str): Имя метода (например, "get_by_id").
            args (tuple): Позиционные аргументы.
            kwargs (dict): Именованные аргументы.

        Возвращает:
            str: Уникальный ключ кэша (например, "UserRepository.get_by_id:user_123").
        """
        # Формируем строку аргументов: "user_123,role=admin"
        args_str = ",".join(str(a) for a in args)
        kwargs_str = ",".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        params = f"{args_str}{kwargs_str}"

        # Имя репозитория: получаем из _repo_factory
        repo_name = self._repo_factory.__name__.replace("_create_", "").replace("_repo", "")

        return f"{repo_name}.{method_name}:{params}"

class DataManager:
    """
    Центральный интерфейс для работы с данными.

    Автоматически:
    - проверяет кэш перед запросом к БД,
    - сохраняет результат в кэш после успешного запроса,
    - управляет транзакциями через Unit of Work.

    Использование:
        async with DataManager(cache_manager, session_maker) as dm:
            user = await dm.users.get_by_id(user_id)
            # если user в кэше — вернётся сразу, иначе — запрос к БД

    Атрибуты:
        cache (CacheManagerInterface): Кэш-сервис (Redis).
        uow (UnitOfWork | None): Unit of Work (если используется транзакция).

    Аргументы:
        cache_manager (CacheManagerInterface): Кэш-сервис.
        session_maker (async_sessionmaker[AsyncSession]): Фабрика сессий.
        default_ttl (timedelta): TTL по умолчанию для кэша (по умолчанию 5 мин).

    Возвращает:
        DataManager: Экземпляр для работы с данными.

    Возможные исключения:
        RuntimeError: если `session_maker` или `cache_manager` не инициализированы.

    Ограничения и допущения:
        - Кэш используется только для read-only операций (get_by_id, get_all и т.д.).
        - Для write-операций (create, update, delete) используется `UnitOfWork`.
        - Инвалидация кэша (при изменении данных) реализуется в `UnitOfWork` или в сервисах.

    Примеры:
        # 1. Простой read-запрос
        dm = DataManager(cache_manager, session_maker)
        user = await dm.users.get_by_id(user_id)

        # 2. Read-запрос с транзакцией
        async with DataManager(cache_manager, session_maker) as dm:
            user = await dm.users.get_by_id(user_id)
            await dm.uow.users.update(user)  # write-операция в UoW

        # 3. Write-транзакция без кэша
        async with DataManager(cache_manager, session_maker) as dm:
            user = UserModel(...)
            await dm.uow.users.create(user)
            # кэш автоматически инвалидируется в UoW
    """

    def __init__(
        self,
        cache_manager: CacheManagerInterface,
        session_maker: async_sessionmaker[AsyncSession],
        default_ttl: timedelta = CACHE_TTL_DEFAULT,
    ):
        self._cache = cache_manager
        self._session_maker = session_maker
        self._default_ttl = default_ttl
        self._uow: UnitOfWork | None = None

    async def __aenter__(self) -> "DataManager":
        self._uow = UnitOfWork(self._session_maker)
        await self._uow.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._uow:
            await self._uow.__aexit__(exc_type, exc_val, exc_tb)
            self._uow = None

    @property
    def users(self) -> "_CachedRepositoryProxy":
        return _CachedRepositoryProxy(
            cache=self._cache,
            repo_factory=self._create_user_repo,
            ttl=self._default_ttl,
        )

    @property
    def teams(self) -> "_CachedRepositoryProxy":
        return _CachedRepositoryProxy(
            cache=self._cache,
            repo_factory=self._create_team_repo,
            ttl=self._default_ttl,
        )

    @property
    def projects(self) -> "_CachedRepositoryProxy":
        return _CachedRepositoryProxy(
            cache=self._cache,
            repo_factory=self._create_project_repo,
            ttl=self._default_ttl,
        )

    @property
    def tasks(self) -> "_CachedRepositoryProxy":
        return _CachedRepositoryProxy(
            cache=self._cache,
            repo_factory=self._create_task_repo,
            ttl=self._default_ttl,
        )

    @property
    def task_executors(self) -> "_CachedRepositoryProxy":
        return _CachedRepositoryProxy(
            cache=self._cache,
            repo_factory=self._create_task_executor_repo,
            ttl=self._default_ttl,
        )

    @property
    def meetings(self) -> "_CachedRepositoryProxy":
        return _CachedRepositoryProxy(
            cache=self._cache,
            repo_factory=self._create_meeting_repo,
            ttl=self._default_ttl,
        )

    @property
    def events(self) -> "_CachedRepositoryProxy":
        return _CachedRepositoryProxy(
            cache=self._cache,
            repo_factory=self._create_event_repo,
            ttl=self._default_ttl,
        )

    def _create_user_repo(self):
        if self._uow:
            return self._uow.users
        return UserRepository(self._session_maker())

    def _create_team_repo(self):
        if self._uow:
            return self._uow.teams
        return TeamRepository(self._session_maker())

    def _create_project_repo(self):
        if self._uow:
            return self._uow.projects
        return ProjectRepository(self._session_maker())

    def _create_task_repo(self):
        if self._uow:
            return self._uow.tasks
        return TaskRepository(self._session_maker())

    def _create_task_executor_repo(self):
        if self._uow:
            return self._uow.task_executors
        return TaskExecutorRepository(self._session_maker())

    def _create_meeting_repo(self):
        if self._uow:
            return self._uow.meetings
        return MeetingRepository(self._session_maker())

    def _create_event_repo(self):
        if self._uow:
            return self._uow.events
        return EventRepository(self._session_maker())