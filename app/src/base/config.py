import contextvars
import logging
import os
from logging import Formatter, getLogger
from pathlib import Path
from typing import Optional, Any
from urllib.parse import quote_plus

from concurrent_log_handler import ConcurrentRotatingFileHandler
from dotenv import load_dotenv
from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Режим разработки
DEVELOPMENT_MODE = True

### Path config ###
APP_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = APP_DIR / "src"
API_DIR = SRC_DIR / "api"
DAL_DIR = SRC_DIR / "dal"
DATA_DIR = SRC_DIR.parent / "data"
DATA_DIR = SRC_DIR.parent / "logging"


ENV_PATH = Path(__file__).resolve().parents[3] / "deploy" / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)



### Uvicorn Config ###
class UvicornConfig(BaseSettings):
    """
    Конфигурация сервера Uvicorn для FastAPI-приложения.

    Реализует централизованное управление параметрами запуска,
    включая адаптивное количество воркеров, таймауты и безопасность.

    Атрибуты:
        host (str): IP-адрес для привязки сервера.
        port (int): Порт сервера (по умолчанию 8000).
        workers (int): Количество процессов обработки запросов.
        reload (bool): Включить авто-перезагрузку (для development).
        log_level (str): Уровень логирования (debug, info, warning, error, critical).
        access_log (bool): Включить access log (в production лучше выключить).
        timeout_keep_alive (int): Таймаут в секундах для keep-alive соединений.
        loop (str): Цикл событий (uvloop — для production).
        http (str): HTTP-протокол (h11 или auto).
        ws (str): WebSockets-движок (websockets или auto).
        lifespan (str): Управление lifespan (auto, on, off).

    Примеры использования:
        config = UvicornConfig()
        uvicorn.run("app.main:app", **config.model_dump())
    """

    model_config = SettingsConfigDict(
        env_file="deploy/.env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="SERVER_",
    )

    host: str = Field(default="0.0.0.0", description="IP-адрес для привязки сервера.")
    port: int = Field(
        default=8000, ge=1, le=65535, description="Порт сервера (1–65535)."
    )
    workers: int = Field(
        default_factory=lambda: (os.cpu_count() or 1) * 2 + 1,
        ge=1,
        description="Количество воркеров (по умолчанию: CPU * 2 + 1).",
    )
    reload: bool = Field(
        default=False,
        description="Включить авто-перезагрузку при изменении кода (development only).",
    )
    log_level: str = Field(
        default="info",
        pattern="^(debug|info|warning|error|critical)$",
        description="Уровень логирования.",
    )
    access_log: bool = Field(default=True, description="Включить access log.")
    timeout_keep_alive: int = Field(
        default=30,
        ge=1,
        le=120,
        description="Таймаут для keep-alive соединений (1–120 сек).",
    )
    loop: str = Field(
        default="uvloop",
        pattern="^(asyncio|uvloop)$",
        description="Цикл событий (uvloop — для максимальной производительности).",
    )
    http: str = Field(
        default="auto", pattern="^(auto|h11|h2)$", description="HTTP-протокол."
    )
    ws: str = Field(
        default="auto", pattern="^(auto|websockets)$", description="WebSocket-движок."
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"debug", "info", "warning", "error", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"log_level должен быть одним из: {allowed}")
        return v.lower()


# 🌟 Глобальный экземпляр конфигурации
uvicorn_config = UvicornConfig()

# Нерекомендуется к использованию, для SQLAdmin
# Используем ContextVar для безопасного доступа к DataManager из любых потоков
# в рамках текущего контекста выполнения (например, внутри async-запроса).
_GLOBAL_DATABASE_MANAGER: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "global_data_manager", 
    default=None
)


class PostgresDatabaseConfig(BaseSettings):
    """
    Конфигурация подключения к PostgreSQL-базе данных.

    Собирает строку подключения из компонентов, валидирует параметры и
    предоставляет метод `build_connection_url()` для получения готовой URL.

    Использует переменные окружения с префиксом `POSTGRES_` (например, POSTGRES_HOST).

    Атрибуты:
        host: str — Хост сервера PostgreSQL (не пустой, валидный домен/IP)
        port: int — Порт (1–65535)
        user: str — Имя пользователя (не пустой)
        password: str | None — Пароль (может быть пустым в dev-средах)
        db_name: str — Имя базы данных (не пустой)
        pool_size: int — Размер пула соединений (по умолчанию 10)
        pool_timeout: int — Таймаут получения соединения из пула (по умолчанию 30)
        max_overflow: int — Максимальное количество дополнительных соединений при перегрузке (по умолчанию 20)
        pool_pre_ping: bool — Проверка соединения перед использованием (по умолчанию True)
        pool_recycle: int — Время жизни соединения до пересоздания (по умолчанию 3600 сек)
        echo: bool — Логировать SQL-запросы (по умолчанию False)

    Возвращаемое значение метода `connection_url`:
        str — Готовая строка подключения, например:
        postgresql+asyncpg://user:pass@host:5432/db

    Возможные исключения:
        ValueError: если не пройдёт валидация (например, пустой `host`)
    """

    model_config = SettingsConfigDict(
        # env_file=find_dotenv(filename=".env", raise_error_if_not_found=False),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="POSTGRES_",
    )

    host: str = Field(..., min_length=1, exclude=True)
    port: int = Field(..., ge=1, le=65535, exclude=True)
    user: str = Field(..., min_length=1, exclude=True)
    password: str | None = Field(default=None, exclude=True)
    db_name: str = Field(..., min_length=1, exclude=True)

    # optional
    echo: bool = Field(default=False,)
    max_overflow: int = Field(default=20, ge=0)
    pool_pre_ping: bool = Field(default=True)
    pool_recycle: int = Field(default=3600, ge=0)
    pool_size: int = Field(default=10, ge=1)
    pool_timeout: int = Field(default=30, ge=1)

    @computed_field
    @property
    def connection_url(self) -> str:
        """Собирает строку подключения к PostgreSQL.

        Внимание: если `password` равен `None`, он не включается в URL.

        Возвращает:
            str — готовая строка подключения, например:
                postgresql+asyncpg://user:password@host:5432/db
        """
        # ✅ Важно: используем quote_plus, чтобы безопасно кодировать спецсимволы в пароле
        password_part = ""
        if self.password:
            password_part = f":{quote_plus(self.password)}"

        return f"postgresql+asyncpg://{self.user}{password_part}@{self.host}:{self.port}/{self.db_name}"

    @field_validator("host")
    @classmethod
    def _validate_host(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Поле `host` не должно быть пустым")
        return v.strip()

    @field_validator("db_name")
    @classmethod
    def _validate_db_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Поле `db_name` не должно быть пустым")
        return v.strip()

    @field_validator("user")
    @classmethod
    def _validate_user(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Поле `user` не должно быть пустым")
        return v.strip()

    @model_validator(mode="after")
    def _validate_after(self) -> PostgresDatabaseConfig:
        """Дополнительная проверка: пароль не должен быть логином."""
        if self.password is not None and self.password == self.user:
            logger.warning(
                "Пароль совпадает с именем пользователя (POSTGRES_PASSWORD=POSTGRES_USER). "
                "Это может быть уязвимостью. Рассмотрите изменение пароля."
            )
        return self


class RedisConfig(BaseSettings):
    """
    Конфигурация подключения к Redis.

    Собирает параметры из переменных окружения с префиксом `REDIS_`.

    Атрибуты:
        host (str): Хост Redis (обязательный, alias=HOST).
        port (int): Порт Redis (по умолчанию 6379, alias=PORT).
        db (int): Номер базы данных (по умолчанию 0, alias=DB).
        password (Optional[str]): Пароль для аутентификации (alias=PASSWORD).
        ssl (bool): Использовать SSL (по умолчанию False, alias=SSL).
    """

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        env_prefix="REDIS_",
        extra="ignore",
    )

    host: str = Field(..., min_length=1)
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0)
    password: Optional[str] = Field(default=None, alias="PASSWORD")
    ssl: bool = Field(default=False, alias="SSL")

    @property
    def connection_url(self) -> str:
        """Возвращает строку подключения к Redis.

        Пример: redis://:password@host:port/db

        Если `password=None`, пароль не включается.
        """
        password_part = f":{self.password}@" if self.password else ""
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{password_part}{self.host}:{self.port}/{self.db}"


# Авторизация
class AuthConfig(BaseSettings):
    """Настройки JWT и безопасности."""

    model_config = SettingsConfigDict(
        env_file=ENV_PATH, env_file_encoding="utf-8", env_prefix="AUTH_", extra="ignore"
    )

    secret_key: str = Field(..., description="Секретный ключ для JWT.")
    token_expiry_minutes: int = Field(
        default=60, description="Время жизни токена доступа в минутах."
    )
    refresh_token_expiry_days: int = Field(
        default=7, description="Время жизни рефреш-токена в днях."
    )
    algorithm: str = Field(default="HS256", description="Алгоритм подписи JWT.")


MAIN_AUTH_CONFIG = AuthConfig()


# Настройка логирования.
LOG_DIR = APP_DIR / "logging"
LOG_DIR.mkdir(exist_ok=True)
log_path = LOG_DIR / "app.log"

loghandler: ConcurrentRotatingFileHandler = ConcurrentRotatingFileHandler(
    filename=str(log_path),
    maxBytes=10 * 1024 * 1024,  # 10 МБ
    backupCount=5,
    encoding="utf-8",
)

loghandler.setFormatter(
    Formatter(
        "%(asctime)s - %(levelname)s - %(message)s - %(filename)s - %(funcName)s - %(lineno)d"
    )
)

# Настраиваем корневой логгер
logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger().addHandler(loghandler)

logger = getLogger(__name__)
