"""Тесты engine.py для управления БД."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock, mock_open
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession

from app.src.dal.database.engine import (
    PostgresDatabaseConfig,
    create_postgre_engine,
    create_sqlite_engine,
    create_session_maker,
    start_engine,
    SQLITE_SUPPORTED,
)


class TestPostgresDatabaseConfig:
    """Тесты PostgresDatabaseConfig."""

    def test_config_validation_empty_host(self):
        """Тест валидации пустого host."""
        with pytest.raises(ValueError, match="host"):
            PostgresDatabaseConfig(
                host="",
                port=5432,
                user="testuser",
                db_name="testdb"
            )

    def test_config_validation_empty_user(self):
        """Тест валидации пустого user."""
        with pytest.raises(ValueError, match="user"):
            PostgresDatabaseConfig(
                host="localhost",
                port=5432,
                user="",
                db_name="testdb"
            )

    def test_config_validation_empty_db_name(self):
        """Тест валидации пустого db_name."""
        with pytest.raises(ValueError, match="db_name"):
            PostgresDatabaseConfig(
                host="localhost",
                port=5432,
                user="testuser",
                db_name=""
            )

    def test_config_validation_port_out_of_range(self):
        """Тест валидации порта за пределами диапазона."""
        with pytest.raises(ValueError):
            PostgresDatabaseConfig(
                host="localhost",
                port=0,  # Недопустимый порт
                user="testuser",
                db_name="testdb"
            )

    def test_connection_url_without_password(self):
        """Тест генерации URL без пароля."""
        config = PostgresDatabaseConfig(
            host="localhost",
            port=5432,
            user="testuser",
            db_name="testdb"
        )
        
        assert config.connection_url == "postgresql+asyncpg://testuser@localhost:5432/testdb"

    def test_connection_url_with_password(self):
        """Тест генерации URL с паролем."""
        config = PostgresDatabaseConfig(
            host="localhost",
            port=5432,
            user="testuser",
            password="secret123",
            db_name="testdb"
        )
        
        assert "secret123" in config.connection_url

    def test_connection_url_with_special_chars_in_password(self):
        """Тест кодирования спецсимволов в пароле."""
        config = PostgresDatabaseConfig(
            host="localhost",
            port=5432,
            user="testuser",
            password="p@ss:w0rd",
            db_name="testdb"
        )
        
        assert "p%40ss%3Aw0rd" in config.connection_url

    def test_password_same_as_user_logs_warning(self, caplog):
        """Тест предупреждения при совпадении пароля и пользователя."""
        with patch("app.src.dal.database.engine.logger") as mock_logger:
            config = PostgresDatabaseConfig(
                host="localhost",
                port=5432,
                user="testuser",
                password="testuser",  # Совпадает с user
                db_name="testdb"
            )
            
            mock_logger.warning.assert_called_once()


class TestCreatePostgreEngine:
    """Тесты create_postgre_engine."""

    def test_create_engine(self):
        """Тест создания PostgreSQL движка."""
        config = PostgresDatabaseConfig(
            host="localhost",
            port=5432,
            user="testuser",
            db_name="testdb"
        )
        
        with patch("app.src.dal.database.engine.create_async_engine") as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            
            engine = create_postgre_engine(config)
            
            assert engine == mock_engine
            mock_create.assert_called_once()


class TestCreateSqliteEngine:
    """Тесты create_sqlite_engine."""

    def test_create_sqlite_engine(self):
        """Тест создания SQLite движка."""
        with patch("app.src.dal.database.engine.create_async_engine") as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            
            engine = create_sqlite_engine()
            
            assert engine == mock_engine
            mock_create.assert_called_once()


class TestCreateSessionMaker:
    """Тесты create_session_maker."""

    def test_create_session_maker(self):
        """Тест создания фабрики сессий."""
        mock_engine = MagicMock()
        
        with patch("app.src.dal.database.engine.async_sessionmaker") as mock_maker:
            mock_session_maker = MagicMock()
            mock_maker.return_value = mock_session_maker
            
            session_maker = create_session_maker(mock_engine)
            
            assert session_maker == mock_session_maker
            mock_maker.assert_called_once()


class TestStartEngine:
    """Тесты start_engine."""

    @pytest.mark.asyncio
    async def test_start_engine_postgresql_success(self):
        """Тест успешного подключения к PostgreSQL."""
        config = PostgresDatabaseConfig(
            host="localhost",
            port=5432,
            user="testuser",
            db_name="testdb"
        )
        
        mock_engine = AsyncMock()
        mock_engine.begin = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock(scalar_one=AsyncMock(return_value=1)))
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn
        
        mock_session_maker = AsyncMock()
        
        with patch("app.src.dal.database.engine.create_postgre_engine", return_value=mock_engine), \
             patch("app.src.dal.database.engine.create_session_maker", return_value=mock_session_maker), \
             patch("app.src.dal.database.engine.logger") as mock_logger:
            
            engine, session_maker = await start_engine(config)
            
            assert engine == mock_engine
            assert session_maker == mock_session_maker
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_start_engine_postgresql_fallback(self):
        """Тест fallback на SQLite при недоступности PostgreSQL."""
        config = PostgresDatabaseConfig(
            host="localhost",
            port=5432,
            user="testuser",
            db_name="testdb"
        )
        
        mock_postgres_engine = AsyncMock()
        mock_postgres_engine.begin = AsyncMock()
        mock_postgres_engine.begin.return_value.__aenter__.side_effect = Exception("Connection refused")
        
        mock_sqlite_engine = AsyncMock()
        mock_sqlite_engine.begin = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock(scalar_one=AsyncMock(return_value=1)))
        mock_sqlite_engine.begin.return_value.__aenter__.return_value = mock_conn
        
        mock_session_maker = AsyncMock()
        
        with patch("app.src.dal.database.engine.create_postgre_engine", return_value=mock_postgres_engine), \
             patch("app.src.dal.database.engine.create_sqlite_engine", return_value=mock_sqlite_engine), \
             patch("app.src.dal.database.engine.create_session_maker", return_value=mock_session_maker), \
             patch("app.src.dal.database.engine.SQLITE_SUPPORTED", True), \
             patch("app.src.dal.database.engine.logger") as mock_logger:
            
            engine, session_maker = await start_engine(config)
            
            assert engine == mock_sqlite_engine
            assert session_maker == mock_session_maker
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_start_engine_no_sqlite_support(self):
        """Тест исключения при недоступности PostgreSQL и отключённом SQLite."""
        config = PostgresDatabaseConfig(
            host="localhost",
            port=5432,
            user="testuser",
            db_name="testdb"
        )
        
        mock_postgres_engine = AsyncMock()
        mock_postgres_engine.begin = AsyncMock()
        mock_postgres_engine.begin.return_value.__aenter__.side_effect = Exception("Connection refused")
        
        with patch("app.src.dal.database.engine.create_postgre_engine", return_value=mock_postgres_engine), \
             patch("app.src.dal.database.engine.SQLITE_SUPPORTED", False):
            
            with pytest.raises(Exception, match="PostgreSQL недоступен"):
                await start_engine(config)
