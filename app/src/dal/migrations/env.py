"""
Контекст выполнения Alembic для асинхронного приложения.

Настраивает подключение к базе данных через асинхронный движок SQLAlchemy.
Использует актуальные модели из `models.Base` для автоматического сравнения схемы (autogenerate).
Поддерживает работу с asyncpg и aiosqlite (опционально).

Важно: использует `run_migrations_online()` как единственный режим — без offline.
"""

import asyncio
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.src.dal.database.engine import PostgresDatabaseConfig

# Наши модели
from app.src.dal.database.models import (
    BaseModel,
    EventModel,
    MeetingModel,
    ProjectModel,
    TaskExecutorModel,
    TaskModel,
    TeamModel,
    UserModel,
)

logger = logging.getLogger(__name__)

# Логирование из Alembic .ini
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные для autogenerate
target_metadata = BaseModel.metadata


def get_url() -> str:
    """
    Возвращает URL базы данных из переменной окружения DATABASE_URL.

    """
    config = PostgresDatabaseConfig()
    return config.connection_url



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


    # 🆕 Проверка подключения перед запуском миграций
    try:
        async with connectable.connect() as connection:
            # Выполняем тестовый запрос
            await connection.execute(text("SELECT 1"))
            logger.info("Подключение к БД успешно")
    except Exception as e:
        logger.critical("Не удалось подключиться к базе данных: %s", e)
        raise RuntimeError("База данных недоступна. Миграции не могут быть применены.") from e

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()



# Запускаем онлайн-миграции
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())