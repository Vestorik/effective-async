"""
Модуль кэширования репозиториев и Unit of Work с Redis.

Допущение:
В CachedUnitOfWork используются типы репоризитриев для обеспечения интерфейса.

Назначение:
    Предоставляет механизмы кэширования на уровне репозиториев и Unit of Work
    для минимизации числа запросов к базе данных. Реализует прокси-паттерн с
    автоматическим извлечением данных из кэша при повторных вызовах.

Архитектура:
    - CachedRepositoryProxy: прокси-обёртка для репозиториев с логикой кэширования
      (GET-операции), реализованная через __getattr__ и functools.wraps для
      сохранения сигнатуры и документации оригинальных методов.
    - CachedUnitOfWork: расширение паттерна Unit of Work, интегрирующее
      кэширование на уровне всего контекста работы с БД.
    - CacheManager: низкоуровневый менеджер взаимодействия с Redis (get, setex,
      delete, clear_pattern).
    - RedisConfig: конфигурация подключения к Redis через pydantic-settings.

Ключевые принципы:
    - DRY: логика кэширования вынесена в общие компоненты.
    - KISS: простой интерфейс без лишней абстракции.
    - Composition over Inheritance: прокси используют композицию с репозиторием.
    - Dependency Injection: все зависимости внедряются через конструкторы.
    - Twelve-Factor App: конфигурация вынесена в переменные окружения.
    - SOLID: соблюдение принципов Single Responsibility и Dependency Inversion.

Кэширование:
    - Кэшируются только read-операции (get_by_id, get_all, get_all_paginated и т.д.).
    - Write-операции (create, update, delete) обходят кэш и идут напрямую в БД.
    - Ключи кэша формируются как "prefix:method_name:arg1:arg2:kw1=val1:kw2=val2"
      с сериализацией list/dict через repr() для уникальности.
    - Время жизни кэша настраивается через time_segment в CachedRepositoryProxy
      или по умолчанию через default_ttl в CacheManager.

Ограничения:
    - IDE не показывает подсказки для динамических методов (работает через TYPE_CHECKING).
    - Кэш не инвалидируется автоматически — требуется ручная инвалидация или
      стратегия TTL (time_segment).
    - Изменяемые аргументы (list, dict) не гарантируют уникальность ключа без
      явной сериализации (используется repr, что может привести к проблемам при
      изменении порядка элементов).
    - Не поддерживает кэширование методов с несериализуемыми аргументами.

Обработка ошибок:
    - При ошибках подключения к Redis (ConnectionError, TimeoutError) логируются
      сообщения через logger, и операции возвращают None/0.
    - Ошибки в оригинальных методах БД пропускаются сквозь кэш, так как кэширование
      применяется только при успешных результатах (result is not None).

Применение:
    - Рекомендуется для кэширования часто читаемых, редко изменяемых данных.
    - Не рекомендуется для данных с высокой частотой обновления (рисик устаревания).
    - Для критичных данных (например, финансовые операции) использовать только
      при согласованной стратегии инвалидации.

Примеры:
    # Инициализация
    config = RedisConfig()
    redis_client = Redis.from_url(config.connection_url)
    cache = CacheManager(redis_client, default_ttl=timedelta(minutes=5))

    # Использование в сервисе
    async with CachedUnitOfWork(db_manager, cache, timedelta(minutes=10)) as uow:
        # Кэшированный GET
        user = await uow.users.get_by_id(1)
        # Повторный вызов — из кэша
        user = await uow.users.get_by_id(1)
        # Write-операция — обходит кэш
        await uow.users.update(user)
"""

import functools
from datetime import timedelta
from logging import getLogger
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from redis.asyncio import Redis

from app.src.base.config import RedisConfig
from app.src.dal.database.session_manage import DataBaseManager

RepositoryLike = TypeVar("RepositoryLike")
logger = getLogger()


class CacheManager:
    """
    Реализация CacheManagerInterface для Redis с DI-поддержкой.

    Хранит экземпляр Redis в `self.redis` и предоставляет методы для работы с кэшем:
    - get: получить значение по ключу.
    - setex: сохранить значение с TTL.
    - delete: удалить ключ.
    - clear_pattern: удалить все ключи по шаблону.

    Атрибуты:
        redis (Redis): Экземпляр подключения к Redis.
        default_ttl (timedelta): Время жизни по умолчанию (для setex).

    Аргументы:
        redis (Redis): Экземпляр Redis (можно создать из `RedisConfig`).
        default_ttl (timedelta): Время жизни по умолчанию.

    Пример:
        config = RedisConfig()
        redis = Redis.from_url(config.connection_url)
        cache = CacheManager(redis, default_ttl=timedelta(minutes=5))
    """

    def __init__(self, redis: Redis, default_ttl: timedelta = timedelta(minutes=5)):
        self.redis = redis
        self.default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            # Если decode_responses=True — возвращаем str, иначе bytes.decode()
            if isinstance(value, bytes):
                return value.decode("utf-8")
            return value
        except (ConnectionError, TimeoutError) as ex:
            logger.error("Ошибка при чтении из кэша (ключ '%s'): %s", key, ex)
            return None

    async def setex(self, key: str, ttl: timedelta, value: Any) -> None:
        try:
            ttl_seconds = int(ttl.total_seconds())
            if ttl_seconds <= 0:
                raise ValueError("TTL должен быть положительным")
            await self.redis.setex(key, ttl_seconds, value)
        except (ConnectionError, TimeoutError) as ex:
            logger.error("Ошибка при записи в кэш (ключ '%s'): %s", key, ex)

    async def delete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except (ConnectionError, TimeoutError) as ex:
            logger.error("Ошибка при удалении ключа '%s': %s", key, ex)

    async def clear_pattern(self, pattern: str) -> int:
        """
        Удаляет все ключи по шаблону.

        ⚠️ ОПАСНО: Использует KEYS — не для продакшена!
        """
        try:
            keys = await self.redis.keys(pattern)
            if not keys:
                return 0
            return await self.redis.delete(*keys)
        except (ConnectionError, TimeoutError) as ex:
            logger.error("Ошибка при очистке по шаблону '%s': %s", pattern, ex)
            return 0


def create_cache_manager_from_config(
    config: RedisConfig | None = None, ttl: timedelta = timedelta(minutes=5)
) -> CacheManager:
    """
    Создаёт CacheManager на основе RedisConfig.

    Инициализирует Redis-подключение и возвращает CacheManager.

    Аргументы:
        config (RedisConfig): Конфигурация Redis.

    Возвращает:
        CacheManager: Готовый к использованию кэш-менеджер.

    Пример:
        config = RedisConfig()
        cache = await create_cache_manager_from_config(config)
    """
    if config is None:
        config = RedisConfig()  # <-- Создаём только при необходимости
    redis_client = Redis.from_url(config.connection_url, decode_responses=False)
    return CacheManager(redis_client, ttl)


class CachedRepositoryProxy(Generic[RepositoryLike]):
    """
    Прокси-обёртка для репозитория с автоматическим кэшированием read-операций.

    Поведение:
        - Перехватывает вызовы методов репозитория через __getattr__.
        - Пытается кэшировать результаты всех вызванных методов
        - Кэширует результаты вызовов методов в Redis с использованием CacheManager.
        - Ключи кэша формируются динамически на основе имени метода и аргументов.
        - Возвращает кэшированное значение при повторном вызове с теми же аргументами.

    Структура:
        - Использует Generic[RepositoryType] для типовой безопасности при статической проверке.
        - Приватные атрибуты (repository_obj, cache_manager, key_prefix, time_segment) инкапсулируют детали реализации.
        - Методы документируются через functools.wraps для сохранения __doc__, __name__, __annotations__.

    Атрибуты:
        __repository_obj (RepositoryType): Оригинальный репозиторий, к которому применяется кэширование.
        __cache (CacheManager): Менеджер кэша (Redis), отвечающий за сохранение и извлечение данных.
        __key_prefix (str): Префикс для формирования уникальных ключей кэша (например, "users", "tasks").
        __time_segment (timedelta): Время жизни кэша для каждого вызова метода.

    Аргументы:
        repository_obj (RepositoryType): Оригинальный репозиторий, методы которого будут кэшироваться.
        cache_manager (CacheManager): Менеджер кэша, предоставляющий методы get(), setex().
        key_prefix (str): Префикс для ключей кэша, позволяющий группировать данные по типу ресурса.
        time_segment (timedelta): Время жизни кэша, определяющее, как долго результаты будут храниться.

    Возвращаемое значение:
        - При вызове метода через __getattr__: асинхронная функция-обёртка, которая сначала проверяет кэш, затем БД, и сохраняет результат в кэш.
        - Возвращаемое значение зависит от оригинального метода репозитория.

    Дополнительная информация:
        - Для формирования ключа используется строка в формате: "prefix:method:arg1:arg2:kw1=val1:kw2=val2".
        - Пустые или None-значения в аргументах обрабатываются как строки.
        - List и dict сериализуются через repr() для уникальности, но это может привести к потере type-совместимости.

    Возможные исключения:
        - ConnectionError: При недоступности Redis во время get() или setex().
        - TimeoutError: При превышении таймаута подключения к Redis.
        - ValueError: Если ttl <= 0 в setex() (внутреннее исключение cache_manager).

    Ограничения и допущения:
        - Не поддерживает кэширование методов с изменяемыми аргументами (например, dict, list) без явной сериализации.
        - Не гарантирует кэширование при ошибках в оригинальном методе (результат не сохраняется).
        - IDE может не показывать подсказки типов для динамических методов (требуется TYPE_CHECKING или Protocol).
        - Кэш не инвалидируется автоматически при изменении данных — инвалидация должна быть реализована на уровне бизнес-логики.

    Примеры вызова:
        # 1. Простое кэширование get_by_id
        repo = UserRepository(session)
        cached_repo = CachedRepositoryProxy(repo, cache_manager, key_prefix="users", time_segment=timedelta(minutes=5))
        user = await cached_repo.get_by_id(1)  # кэшируется
        user = await cached_repo.get_by_id(1)  # возвращается из кэша

        # 2. Кэширование с пагинацией
        tasks = await cached_repo.get_all_paginated(skip=0, limit=10)  # кэшируется
        # При изменении skip или limit будет создан новый ключ кэша

        # 3. Некэшируемые методы
        await cached_repo.create(user_data)  # передаётся напрямую, не кэшируется
        await cached_repo.update(user_data)  # передаётся напрямую, не кэшируется
    """

    def __init__(
        self,
        repository_obj: RepositoryLike,
        cache_manager: CacheManager,
        key_prefix: str,
        time_segment: timedelta,
    ):
        self.__repository_obj = repository_obj
        self.__cache = cache_manager
        self.__key_prefix = key_prefix
        self.__time_segment = time_segment

    def __getattr__(self, name: str):

        attr = getattr(self.__repository_obj, name)

        if not callable(attr):
            return attr

        @functools.wraps(attr)
        async def wrapper(*args, **kwargs):
            # Формируем ключ: "tasks:get_by_id:123:..."
            cache_key = self.__make_cache_key(name, args, kwargs)

            # 1. Попытка из кэша
            cached_value = await self.__cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 2. Запрос к БД
            result = await attr(*args, **kwargs)

            # 3. Сохраняем в кэш
            if result is not None:
                await self.__cache.setex(cache_key, self.__time_segment, result)

            return result

        return wrapper

    def __make_cache_key(self, method_name: str, args: tuple, kwargs: dict) -> str:
        """
        Генерирует уникальный ключ: `prefix:method:arg1:arg2:kw1=val1:kw2=val2`
        """

        def serialize(x):
            return str(x) if not isinstance(x, (list, dict)) else repr(x)

        arg_strs = [serialize(a) for a in args]
        kw_strs = [f"{k}={serialize(v)}" for k, v in sorted(kwargs.items())]
        return f"{self.__key_prefix}:{method_name}:{':'.join(arg_strs + kw_strs)}"


class CachedUnitOfWork:
    """
    Реализация Unit of Work с автоматическим кэшированием read-операций.

    Поведение:
        - Оборачивает стандартный UnitOfWork в прокси-обёртки с кэшированием.
        - Кэширует результаты методов get_by_id, get_all, get_all_paginated и других read-методов.
        - Не кэширует write-методы (create, update, delete) — они проходят напрямую к репозиторию.
        - Инвалидация кэша реализуется через переопределение key_prefix при создании прокси.

    Структура:
        - Использует `TYPE_CHECKING` для IDE-подсказок без влияния на runtime.
        - В runtime все атрибуты (users, teams и т.д.) имеют тип `CachedRepositoryProxy[RepositoryType]`.
        - Строки документации методов репозиториев копируются через `functools.wraps`.

    Атрибуты:
        __database_manger (DataBaseManager): Менеджер базы данных для получения UnitOfWork.
        __cache_manager (CacheManager): Менеджер кэша (Redis) для хранения данных.
        __time_segment (timedelta): Время жизни кэша для всех read-операций.
        __uow (UnitOfWork | None): Ссылка на оригинальный UnitOfWork (устанавливается в __aenter__).
        users (CachedRepositoryProxy[UserRepository]): Кэширующий прокси для UserRepository.
        teams (CachedRepositoryProxy[TeamRepository]): Кэширующий прокси для TeamRepository.
        projects (CachedRepositoryProxy[ProjectRepository]): Кэширующий прокси для ProjectRepository.
        tasks (CachedRepositoryProxy[TaskRepository]): Кэширующий прокси для TaskRepository.
        task_executors (CachedRepositoryProxy[TaskExecutorRepository]): Кэширующий прокси для TaskExecutorRepository.
        meetings (CachedRepositoryProxy[MeetingRepository]): Кэширующий прокси для MeetingRepository.
        events (CachedRepositoryProxy[EventRepository]): Кэширующий прокси для EventRepository.

    Аргументы:
        database (DataBaseManager): Менеджер базы данных.
        cache_manager (CacheManager): Менеджер кэша.
        time_segment (timedelta): Время жизни кэша по умолчанию.

    Пример использования:
        # 1. Базовое использование с кэшированием
        async with CachedUnitOfWork(session_maker, cache_manager, timedelta(minutes=5)) as uow:
            user = await uow.users.get_by_id(user_id)  # кэшируется
            user.name = "New"
            await uow.users.update(user)  # инвалидация кэша (если реализована в UoW)

        # 2. Взаимодействие с несколькими репозиториями
        async with CachedUnitOfWork(session_maker, cache_manager, timedelta(minutes=10)) as uow:
            users = await uow.users.get_all()  # кэшируется
            projects = await uow.projects.get_all_paginated(skip=0, limit=10)  # кэшируется
            await uow.teams.create(team_data)  # не кэшируется, передаётся напрямую
    """

    def __init__(
        self,
        database: DataBaseManager,
        cache_manager: CacheManager,
        time_segment: timedelta,
    ):
        self.__database_manger: DataBaseManager = database
        self.__cache_manager: CacheManager = cache_manager
        self.__time_segment: timedelta = time_segment

    async def __aenter__(self) -> CachedUnitOfWork:
        if TYPE_CHECKING:
            from app.src.dal.database.repositories import (
                EventRepository,
                MeetingRepository,
                ProjectRepository,
                TaskExecutorRepository,
                TaskRepository,
                TeamRepository,
                UserRepository,
            )

            self.users: UserRepository
            self.teams: TeamRepository
            self.projects: ProjectRepository
            self.tasks: TaskRepository
            self.task_executors: TaskExecutorRepository
            self.meetings: MeetingRepository
            self.events: EventRepository

        self.__uow = await self.__database_manger.uow().__aenter__()

        # Создаём прокси для каждого репозитория
        self.users = CachedRepositoryProxy(  # ty:ignore[invalid-assignment] Проверка типов отключена для создания интерфейса, в рантайме все объекты будут CachedRepositoryProxy[RepositoryType]
            repository_obj=self.__uow.users,
            cache_manager=self.__cache_manager,
            key_prefix="users",
            time_segment=self.__time_segment,
        )
        self.teams = CachedRepositoryProxy(  # ty:ignore[invalid-assignment]
            repository_obj=self.__uow.teams,
            cache_manager=self.__cache_manager,
            key_prefix="teams",
            time_segment=self.__time_segment,
        )
        self.projects = CachedRepositoryProxy(  # ty:ignore[invalid-assignment]
            repository_obj=self.__uow.projects,
            cache_manager=self.__cache_manager,
            key_prefix="projects",
            time_segment=self.__time_segment,
        )
        self.tasks = CachedRepositoryProxy(  # ty:ignore[invalid-assignment]
            repository_obj=self.__uow.tasks,
            cache_manager=self.__cache_manager,
            key_prefix="tasks",
            time_segment=self.__time_segment,
        )
        self.task_executors = CachedRepositoryProxy(  # ty:ignore[invalid-assignment]
            repository_obj=self.__uow.task_executors,
            cache_manager=self.__cache_manager,
            key_prefix="task_executors",
            time_segment=self.__time_segment,
        )
        self.meetings = CachedRepositoryProxy(  # ty:ignore[invalid-assignment]
            repository_obj=self.__uow.meetings,
            cache_manager=self.__cache_manager,
            key_prefix="meetings",
            time_segment=self.__time_segment,
        )
        self.events = CachedRepositoryProxy(  # ty:ignore[invalid-assignment]
            repository_obj=self.__uow.events,
            cache_manager=self.__cache_manager,
            key_prefix="events",
            time_segment=self.__time_segment,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.__uow.__aexit__(exc_type, exc_val, exc_tb)
