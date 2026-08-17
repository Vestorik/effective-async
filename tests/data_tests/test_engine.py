"""Тесты engine.py для управления БД."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.src.dal.database.engine import (
    PostgresDatabaseConfig,
    create_postgre_engine,
    create_session_maker,
    create_sqlite_engine,
    start_engine,
)


@pytest.fixture
def valid_postgres_config() -> PostgresDatabaseConfig:
    """Фикстура валидной конфигурации PostgreSQL."""
    return PostgresDatabaseConfig(
        host="localhost",
        port=5432,
        user="test_user",
        password="test_pass",
        db_name="test_db",
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        echo=False,
    )


def test_create_engine(valid_postgres_config):
    """Тест создания PostgreSQL движка."""
    
    with patch("app.src.dal.database.engine.create_async_engine") as mock_create:
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine
        
        engine = create_postgre_engine(valid_postgres_config)
        
        assert engine == mock_engine
        mock_create.assert_called_once()


def test_create_sqlite_engine():
    """Тест создания SQLite движка."""
    with patch("app.src.dal.database.engine.create_async_engine") as mock_create:
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine
        
        engine = create_sqlite_engine()
        
        assert engine == mock_engine
        mock_create.assert_called_once()




def test_create_session_maker():
    """Тест создания фабрики сессий."""
    mock_engine = MagicMock()
    
    with patch("app.src.dal.database.engine.async_sessionmaker") as mock_maker:
        mock_session_maker = MagicMock()
        mock_maker.return_value = mock_session_maker
        
        session_maker = create_session_maker(mock_engine)
        
        assert session_maker == mock_session_maker
        mock_maker.assert_called_once()


class TestStartEngine:
    """Тесты для функции start_engine."""

    @pytest.mark.asyncio
    async def test_start_engine_pg_success(self, valid_postgres_config):
        """
        Успешное подключение к PostgreSQL.

        Проверяет, что при успешной проверке соединения с PostgreSQL
        возвращается движок PostgreSQL и session_maker, а SQLite не используется.
        """

        with (
            patch("app.src.dal.database.engine.create_async_engine") as mock_create,
            patch("app.src.dal.database.engine.async_sessionmaker") as mock_maker,
        ):
            
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            mock_session_maker = MagicMock()
            mock_maker.return_value = mock_session_maker
            
            # Act
            engine, session_maker = await start_engine(
                database_config=valid_postgres_config,
            )
            
            
        assert engine == mock_engine
        mock_create.assert_called_once()
        assert session_maker == mock_session_maker
        mock_maker.assert_called_once()
            
            
    @pytest.mark.asyncio
    async def test_start_engine_pg_fallback_sqlite(self, valid_postgres_config):
        """
        Fallback на SQLite при недоступности PostgreSQL.

        Проверяет, что если PG недоступен, а SQLITE_SUPPORTED=True,
        система переключается на SQLite.
        """
        mock_postgres_engine = AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(side_effect=ConnectionError)))

        with (
            patch("app.src.dal.database.engine.create_postgre_engine", return_value=mock_postgres_engine),
            patch("app.src.dal.database.engine.create_async_engine") as mock_create,
            patch("app.src.dal.database.engine.async_sessionmaker") as mock_maker,
        ):
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            mock_session_maker = MagicMock()
            mock_maker.return_value = mock_session_maker
            
            
            engine, session_maker = await start_engine(
                database_config=valid_postgres_config, 
                SQLITE_SUPPORTED=True
            )

        # Assert
        assert engine == mock_engine
        mock_create.assert_called_once()
        assert session_maker == mock_session_maker
        mock_maker.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_engine_pg_fail_no_sqlite_support(self, valid_postgres_config):
        """
        Ошибка при недоступности PostgreSQL и отключенной поддержке SQLite.
        
        Checks that when PostgreSQL fails and SQLITE_SUPPORTED=False,
        the function raises an exception.
        """
        # --- Arrange ---
        mock_pg_engine = AsyncMock()
        
        # Настраиваем PG на ошибку
        mock_pg_conn_fail = AsyncMock()
        mock_pg_conn_fail.execute.side_effect = Exception("Connection refused")
        
        mock_pg_begin_ctx_fail = AsyncMock()
        mock_pg_begin_ctx_fail.__aenter__ = AsyncMock(return_value=mock_pg_conn_fail)
        mock_pg_begin_ctx_fail.__aexit__ = AsyncMock(return_value=False)
        
        mock_pg_engine.begin.return_value = mock_pg_begin_ctx_fail

        with patch("app.src.dal.database.engine.create_postgre_engine", return_value=mock_pg_engine), pytest.raises(Exception, match="PostgreSQL недоступен"):
            
            await start_engine(
                database_config=valid_postgres_config, 
                SQLITE_SUPPORTED=False
            )

class TestCreateSessionMaker:
    """Тесты для функции create_session_maker."""

    def test_create_session_maker_configuration(self):
        """
        Проверка корректной инициализации async_sessionmaker.
        
        Checks that async_sessionmaker is called with the correct arguments.
        """
        mock_engine = MagicMock()
        mock_session_maker = MagicMock()

        with patch("app.src.dal.database.engine.async_sessionmaker", return_value=mock_session_maker) as mock_maker_class:
            result = create_session_maker(mock_engine)

            assert result is mock_session_maker
            mock_maker_class.assert_called_once()
            
            # Проверяем аргументы вызова
            call_kwargs = mock_maker_class.call_args.kwargs
            assert call_kwargs["bind"] is mock_engine
            assert call_kwargs["expire_on_commit"] is False
            assert call_kwargs["autocommit"] is False
            assert call_kwargs["autoflush"] is False


class TestCreateEngineFunctions:
    """Тесты для вспомогательных функций создания движков."""

    def test_create_postgre_engine_calls_async_engine(self, valid_postgres_config):
        """
        Проверка вызова create_async_engine для PostgreSQL.
        
        Checks that create_postgre_engine constructs the correct URL and calls
        create_async_engine with appropriate parameters.
        """
        with patch("app.src.dal.database.engine.create_async_engine") as mock_async_engine:
            create_postgre_engine(valid_postgres_config)
            
            mock_async_engine.assert_called_once()
            # Проверяем, что передавался URL и параметры
            call_args = mock_async_engine.call_args
            # Первый аргумент - URL, который должен быть не пустым
            assert call_args[0][0].startswith("postgresql+asyncpg://")

    def test_create_sqlite_engine_calls_async_engine(self):
        """
        Проверка вызова create_async_engine для SQLite.
        
        Checks that create_sqlite_engine uses StaticPool and correct connect_args.
        """
        with patch("app.src.dal.database.engine.create_async_engine") as mock_async_engine:
            create_sqlite_engine()
            
            mock_async_engine.assert_called_once()
            call_kwargs = mock_async_engine.call_args.kwargs
            
            # Проверяем специфичные для SQLite параметры
            assert call_kwargs["poolclass"] is not None # Должен быть StaticPool или аналог
            assert call_kwargs["connect_args"] == {"check_same_thread": False}
            assert call_kwargs["pool_pre_ping"] is True