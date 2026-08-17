# tests/data_tests/test_repository/test_task_executor_repository.py

"""
Тесты для TaskExecutorRepository.

Критерии приемки:
1. get_by_id: возвращает исполнителя задачи по ID или None.
2. get_by_task_and_user: возвращает запись исполнителя по задаче и пользователю.
3. delete_by_task_and_user: удаляет связь задачи и пользователя.
4. get_executors_for_task: возвращает список исполнителей задачи.
5. get_tasks_for_user: возвращает пагинированный список задач пользователя.

Тестирование выполнено через мокирование AsyncSession.
Не создаются реальные модели БД, используются моки с spec на реальные модели.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.src.dal.database.repositories import TaskExecutorRepository
from app.src.dal.database.models import TaskExecutorModel, TaskModel, UserModel


@pytest.fixture
def mock_session() -> AsyncMock:
    """
    Создает мок асинхронной сессии.
    
    Возвращает:
        AsyncMock: Мокированная сессия SQLAlchemy.
    """
    session = AsyncMock(spec=AsyncSession)
    
    # Подготовка скалярного результата для запросов
    scalar_result = MagicMock()
    scalar_result.first.return_value = None
    scalar_result.unique.return_value = scalar_result
    
    session.get.return_value = None
    session.add = AsyncMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute.return_value = MagicMock()
    session.scalars.return_value = scalar_result
    
    return session


@pytest.fixture
def mock_task_executor() -> MagicMock:
    """
    Создает мок исполнителя задачи.
    
    Возвращает:
        MagicMock: Мокированный объект TaskExecutorModel.
    """
    executor = MagicMock(spec=TaskExecutorModel)
    executor.id = uuid4()
    executor.task_id = uuid4()
    executor.user_id = uuid4()
    return executor


@pytest.fixture
def mock_user() -> MagicMock:
    """
    Создает мок пользователя.
    
    Возвращает:
        MagicMock: Мокированный объект UserModel.
    """
    user = MagicMock(spec=UserModel)
    user.id = uuid4()
    return user


@pytest.fixture
def mock_task() -> MagicMock:
    """
    Создает мок задачи.
    
    Возвращает:
        MagicMock: Мокированный объект TaskModel.
    """
    task = MagicMock(spec=TaskModel)
    task.id = uuid4()
    return task


@pytest.fixture
def task_executor_repo(mock_session) -> TaskExecutorRepository:
    """
    Создает экземпляр TaskExecutorRepository с моковой сессией.
    
    Args:
        mock_session: Мокированная сессия.
        
    Returns:
        TaskExecutorRepository: Экземпляр репозитория.
    """
    return TaskExecutorRepository(session=mock_session)


class TestTaskExecutorRepository:
    """Тесты для TaskExecutorRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        task_executor_repo: TaskExecutorRepository,
        mock_task_executor: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает исполнителя задачи при успешном поиске по ID.
        
        Arrange: Мокируем session.get для возврата исполнителя.
        Act: Вызов get_by_id.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        executor_id = mock_task_executor.id
        mock_session.get.return_value = mock_task_executor

        # Act
        result = await task_executor_repo.get_by_id(executor_id)

        # Assert
        mock_session.get.assert_called_once_with(TaskExecutorModel, executor_id)
        assert result == mock_task_executor

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        task_executor_repo: TaskExecutorRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает None, если исполнитель не найден.
        
        Arrange: Мокируем session.get для возврата None.
        Act: Вызов get_by_id.
        Assert: Результат равен None.
        """
        # Arrange
        executor_id = uuid4()
        mock_session.get.return_value = None

        # Act
        result = await task_executor_repo.get_by_id(executor_id)

        # Assert
        mock_session.get.assert_called_once_with(TaskExecutorModel, executor_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_task_and_user_success(
        self,
        task_executor_repo: TaskExecutorRepository,
        mock_task_executor: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_task_and_user возвращает исполнителя задачи по задаче и пользователю.
        
        Arrange: Мокируем результат scalars.first().
        Act: Вызов get_by_task_and_user.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        task_id = mock_task_executor.task_id
        user_id = mock_task_executor.user_id
        
        mock_scalar_result = MagicMock()
        mock_scalar_result.first.return_value = mock_task_executor
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        result = await task_executor_repo.get_by_task_and_user(task_id, user_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert result == mock_task_executor

    @pytest.mark.asyncio
    async def test_get_by_task_and_user_not_found(
        self,
        task_executor_repo: TaskExecutorRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_task_and_user возвращает None, если исполнитель не найден.
        
        Arrange: Мокируем результат scalars.first() для возврата None.
        Act: Вызов get_by_task_and_user.
        Assert: Результат равен None.
        """
        # Arrange
        task_id = uuid4()
        user_id = uuid4()
        
        mock_scalar_result = MagicMock()
        mock_scalar_result.first.return_value = None
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        result = await task_executor_repo.get_by_task_and_user(task_id, user_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert result is None


    @pytest.mark.asyncio
    async def test_get_executors_for_task_success(
        self,
        task_executor_repo: TaskExecutorRepository,
        mock_user: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_executors_for_task возвращает список исполнителей задачи.
        
        Arrange: Мокируем результат scalars.unique().all().
        Act: Вызов get_executors_for_task.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        task_id = uuid4()
        
        mock_scalar_result = MagicMock()
        mock_scalar_result.unique.return_value.all.return_value = [mock_user]
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        executors = await task_executor_repo.get_executors_for_task(task_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert len(executors) == 1
        assert executors[0] == mock_user

    @pytest.mark.asyncio
    async def test_get_tasks_for_user_success(
        self,
        task_executor_repo: TaskExecutorRepository,
        mock_task: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_tasks_for_user возвращает пагинированный список задач пользователя.
        
        Arrange: Мокируем результаты execute (для count) и scalars (для данных).
        Act: Вызов get_tasks_for_user.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        user_id = mock_task.id # Используем id задачи как user_id для простоты мока, в реальности это user.id
        page = 1
        page_size = 10
        
        # Мокируем результат для count
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 10
        
        # Мокируем результат для данных
        mock_data_result = MagicMock()
        mock_data_result.unique.return_value.all.return_value = [mock_task]
        
        # side_effect позволяет возвращать разные результаты для последовательных вызовов
        mock_session.execute.side_effect = [mock_count_result]
        mock_session.scalars.side_effect = [mock_data_result]

        # Act
        tasks, total = await task_executor_repo.get_tasks_for_user(user_id, page, page_size)

        # Assert
        assert total == 10
        assert len(tasks) == 1
        assert tasks[0] == mock_task
        # Проверяем, что execute был вызван для count
        assert mock_session.execute.call_count == 1
        # Проверяем, что scalars был вызван для данных
        assert mock_session.scalars.call_count == 1