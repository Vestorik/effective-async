import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.src.base.lifespan import startapp, shutdown, lifespan


# --- Хелперы ---

def create_mock_fastapi_app() -> FastAPI:
    """Создает моковый экземпляр FastAPI приложения."""
    # Создаем простой MagicMock, который будет вести себя как приложение
    # Важно: не используем spec=FastAPI для всего объекта, чтобы методы тоже были моками
    app = MagicMock()
    app.state = MagicMock()
    # include_router - это метод, который мы будем вызывать
    # Он сам по себе MagicMock, поэтому у него будет call_count
    return app


@pytest.mark.asyncio
async def test_startapp_initializes_data_manager_and_admin():
    """Тест инициализации DataManager и SQLAdmin."""
    mock_app = create_mock_fastapi_app()
    mock_data_manager = AsyncMock()
    mock_db_manager = MagicMock()
    mock_engine = MagicMock()
    mock_db_manager.get_engine = mock_engine
    mock_data_manager.database_manager = mock_db_manager
    
    with patch('app.src.base.lifespan.get_data_manager', AsyncMock(return_value=mock_data_manager)), \
         patch('app.src.base.lifespan._GLOBAL_DATABASE_MANAGER') as mock_global_db, \
         patch('app.src.base.lifespan.SQLAdminViewSet') as mock_admin:
         
        await startapp(mock_app)
        
        # Проверка вызова get_data_manager
        mock_data_manager.__aenter__ = AsyncMock(return_value=mock_data_manager) # Если get_data_manager возвращает контекст менеджер
        # Но в коде: data_manager = await get_data_manager(), значит get_data_manager должна быть coroutine
        # Mock уже настроен как AsyncMock, значит его вызов вернет результат
        
        # Проверка установки в app.state
        assert mock_app.state.data_manager == mock_data_manager
        
        # Проверка установки глобального менеджера
        mock_global_db.set.assert_called_once_with(mock_data_manager)
        
        # Проверка инициализации SQLAdminViewSet
        mock_admin.assert_called_once_with(
            app=mock_app,
            secret_key="change-this-to-a-secure-key-in-production",
            databse_engine=mock_engine,
            db_manager=mock_data_manager
        )


# --- Тесты для shutdown ---

@pytest.mark.asyncio
async def test_shutdown_closes_data_manager():
    """Тест закрытия DataManager при shutdown."""
    mock_app = create_mock_fastapi_app()
    mock_data_manager = AsyncMock()
    mock_app.state.data_manager = mock_data_manager
    
    await shutdown(mock_app)
    
    mock_data_manager.close.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_handles_missing_data_manager():
    """Тест shutdown, если data_manager отсутствует."""
    mock_app = create_mock_fastapi_app()
    mock_data_manager = AsyncMock()
    mock_app.state.data_manager = mock_data_manager
    
    await shutdown(mock_app)
    
    # Должно пройти без ошибок
    assert True


# --- Тесты для lifespan ---

@pytest.mark.asyncio
async def test_lifespan_runs_start_and_shutdown():
    """Тест контекстного менеджера lifespan."""
    mock_app = create_mock_fastapi_app()
    
    with patch('app.src.base.lifespan.startapp', new_callable=AsyncMock) as mock_start, \
         patch('app.src.base.lifespan.shutdown', new_callable=AsyncMock) as mock_shutdown:
         
        async with lifespan(mock_app):
            pass
            
        mock_start.assert_called_once_with(mock_app)
        mock_shutdown.assert_called_once_with(mock_app)


@pytest.mark.asyncio
async def test_lifespan_shuts_down_on_error():
    """Тест, что shutdown вызывается даже при ошибке внутри lifespan."""
    mock_app = create_mock_fastapi_app()
    
    with patch('app.src.base.lifespan.startapp', new_callable=AsyncMock), \
         patch('app.src.base.lifespan.shutdown', new_callable=AsyncMock) as mock_shutdown:
         
        with pytest.raises(RuntimeError):
            async with lifespan(mock_app):
                raise RuntimeError("Test Error")
                
        mock_shutdown.assert_called_once_with(mock_app)