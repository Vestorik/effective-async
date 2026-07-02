"""
Модуль для асинхронного подключения к Redis и управления кэшем.

Реализует паттерн "Singleton" через контекстные переменности (ContextVar) для безопасной работы в асинхронной среде.
Предоставляет функции для получения соединения, установки, получения и удаления значений из кэша.
Поддерживает сериализацию/десериализацию через msgspec (высокая производительность).

Зависимости:
    - redis >= 7.4.0
    - msgspec
    - logging

Используется как часть слоя кэширования в сервисах (UserService, TourService и др.).
"""

from redis.asyncio import Redis
from contextvars import ContextVar
from typing import Optional, Any
import msgspec
import logging

logger = logging.getLogger(__name__)

# Контекстная переменная для хранения экземпляра Redis
redis_context: ContextVar[Optional[Redis]] = ContextVar("redis_connection", default=None)


def get_redis() -> Redis:
    """
    Возвращает текущий экземпляр Redis из контекста.

    Используется для внедрения зависимости в обработчики и сервисы.

    Возвращаемое значение:
        Redis - Активное соединение с Redis.

    Исключения:
        ValueError: Если соединение не было установлено.

    Пример:
        redis = get_redis()
        await redis.set("key", "value")
    """
    redis = redis_context.get()
    if redis is None:
        raise ValueError("Соединение с Redis не инициализировано. Вызовите setup_redis() сначала.")
    return redis


async def setup_redis(host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None) -> Redis:
    """
    Инициализирует соединение с Redis и сохраняет его в контексте.

    Выполняет проверку подключения через ping. Поддерживает аутентификацию.

    Аргументы:
        host: str - Хост Redis-сервера.
        port: int - Порт Redis-сервера.
        db: int - Номер базы данных.
        password: Optional[str] - Пароль для аутентификации (если требуется).

    Возвращаемое значение:
        Redis - Настроенный и проверенный клиент Redis.

    Исключения:
        ConnectionError: Если не удалось подключиться к Redis.
        Exception: При других ошибках инициализации.

    Пример:
        await setup_redis(host="redis", port=6379, password="secret")
    """
    try:
        logger.info("Попытка подключения к Redis: %s:%d, db=%d", host, port, db)
        redis: Redis = Redis(host=host, port=port, db=db, password=password, decode_responses=False)

        # Проверка соединения
        pong = await redis.ping()
        if not pong:
            raise ConnectionError("Redis ответил на ping, но вернул False")

        logger.info("Подключение к Redis успешно")
        redis_context.set(redis)
        return redis

    except Exception as e:
        logger.critical("Не удалось подключиться к Redis: %s", e, exc_info=True)
        raise ConnectionError(f"Ошибка подключения к Redis: {e}") from e


async def close_redis() -> None:
    """
    Закрывает соединение с Redis и очищает контекст.

    Должно вызываться при завершении приложения (например, через shutdown handler в LiteStar).
    Безопасно вызывать даже если соединение не было установлено.

    Пример:
        await close_redis()
    """
    redis = redis_context.get()
    if redis:
        try:
            await redis.close()
            logger.info("Соединение с Redis закрыто")
        except Exception as e:
            logger.error("Ошибка при закрытии соединения с Redis: %s", e, exc_info=True)
        finally:
            redis_context.set(None)


async def cache_set(key: str, value: Any, expire: Optional[int] = 300) -> bool:
    """
    Сохраняет объект в Redis с опциональным временем жизни.

    Объект сериализуется через msgspec.json.encode для высокой производительности.
    Не логирует чувствительные данные.

    Аргументы:
        key: str - Уникальный ключ в кэше.
        value: Any - Объект для кэширования (должен быть сериализуемым).
        expire: Optional[int] - Время жизни в секундах. По умолчанию — 300 сек (5 минут).

    Возвращаемое значение:
        bool - True, если сохранение прошло успешно.

    Исключения:
        RuntimeError: Если соединение с Redis не установлено.
        TypeError: Если объект не может быть сериализован.

    Пример:
        await cache_set("user:123", user_model, expire=600)
    """
    try:
        redis = get_redis()
        serialized = msgspec.json.encode(value)
        await redis.set(key, serialized, ex=expire)
        logger.debug("Кэширование успешное: ключ=%s, срок=%s сек", key, expire)
        return True
    except Exception as e:
        logger.warning("Не удалось закэшировать данные по ключу %s: %s", key, e)
        return False


async def cache_get(key: str, type_: type) -> Optional[Any]:
    """
    Получает и десериализует объект из кэша по ключу.

    Возвращает строго типизированный объект. Если ключ не найден — возвращает None.

    Аргументы:
        key: str - Ключ в кэше.
        type_: type - Тип, в который нужно преобразовать данные (например, UserResponse).

    Возвращаемое значение:
        Optional[Any] - Десериализованный объект или None.

    Пример:
        user = await cache_get("user:123", UserResponse)
    """
    try:
        redis = get_redis()
        data = await redis.get(key)
        if data is None:
            logger.debug("Кэш промах: ключ %s не найден", key)
            return None

        obj = msgspec.json.decode(data, type=type_)
        logger.debug("Кэш хит: ключ %s", key)
        return obj
    except Exception as e:
        logger.warning("Ошибка при чтении из кэша по ключу %s: %s", key, e)
        return None


async def cache_delete(key: str) -> bool:
    """
    Удаляет ключ из кэша.

    Используется для инвалидации кэша при обновлении или удалении сущности.

    Аргументы:
        key: str - Ключ для удаления.

    Возвращаемое значение:
        bool - True, если операция выполнена (независимо от существования ключа).

    Пример:
        await cache_delete("user:123")
    """
    try:
        redis = get_redis()
        await redis.delete(key)
        logger.debug("Ключ удалён из кэша: %s", key)
        return True
    except Exception as e:
        logger.warning("Ошибка при удалении ключа %s из кэша: %s", key, e)
        return False