"""
Контекст выполнения Alembic для асинхронного приложения.

Настраивает подключение к базе данных через асинхронный движок SQLAlchemy.
Использует актуальные модели из `models.Base` для автоматического сравнения схемы (autogenerate).
Поддерживает работу с asyncpg и aiosqlite (опционально).

Важно: использует `run_migrations_online()` как единственный режим — без offline.
"""

from logging.config import fileConfig
import asyncio
from typing import cast

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from alembic import context

# Наши модели
from app.src.dal.models import BaseModel
from app.src.dal.engine import SQLITE_SUPPORTED

# Логирование из Alembic .ini
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные для autogenerate
target_metadata = BaseModel.metadata


def get_url() -> str:
    """
    Возвращает URL базы данных из переменной окружения DATABASE_URL.

    Если не задан — пытается использовать SQLite как fallback (если разрешено).
    Иначе вызывает исключение.

    Возвращает:
        str: Строка подключения (например, postgresql+asyncpg://...)
    
    Вызывает:
        RuntimeError: Если DATABASE_URL не задан и SQLite недоступен.
    """
    from os import getenv

    database_url = getenv("DATABASE_URL")
    if database_url:
        return database_url

    if SQLITE_SUPPORTED:
        from pathlib import Path

        path_database = Path(__file__).parent / "data" / ".database.db"
        return f"sqlite+aiosqlite:///{path_database}"

    raise RuntimeError("DATABASE_URL не задан, а поддержка SQLite отключена")


def run_migrations_offline() -> None:
    """
    Не используется — режим offline не поддерживается для асинхронных движков.
    """
    raise NotImplementedError("Offline режим не поддерживается в асинхронном приложении")


def do_run_migrations(connection: Connection) -> None:
    """
    Выполняет применение миграций через указанный connection.

    Аргументы:
        connection (Connection): Активное соединение с БД.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # Отслеживать изменения типов полей
        render_as_batch=True,  # Для SQLite, но безопасно и для Postgres
        include_schemas=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Подключается к БД асинхронно и применяет миграции.

    Создаёт асинхронный движок на основе DATABASE_URL.
    Автоматически определяет диалект (PostgreSQL или SQLite).
    """
    configuration_url = get_url()
    dialect_name = "postgresql" if "postgresql" in configuration_url else "sqlite"

    connectable = create_async_engine(
        configuration_url,
        poolclass=pool.NullPool,
        echo=False,
    )

    async with connectable.connect() as connection:
        # Для асинхронности нужно передать "поддельный" контекст
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# Запускаем онлайн-миграции
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())