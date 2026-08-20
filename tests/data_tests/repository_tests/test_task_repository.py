# tests/data_tests/test_repository/test_task_repository.py

"""
Тесты для TaskRepository.

Критерии приемки:
1. get_by_id: возвращает задачу по ID или None.
2. get_by_project_id: возвращает все задачи проекта.
3. get_by_user_id: возвращает задачи, где пользователь — исполнитель.
4. get_sub_tasks: возвращает подзадачи родительской задачи.
5. get_parent_task: возвращает родительскую задачу для подзадачи.
6. get_tasks_by_team_and_priority: возвращает задачи команды с фильтрацией по приоритету.

Тестирование выполнено через мокирование AsyncSession.
Используются реальные модели из проекта для обеспечения корректности связей.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.src.dal.database.repositories import TaskRepository
from app.src.dal.database.models import TaskModel, TaskExecutorModel, UserModel


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
    session.execute.return_value = scalar_result
    session.scalars.return_value = scalar_result
    
    return session


@pytest.fixture
def mock_task() -> MagicMock:
    """
    Создает мок задачи.
    
    Возвращает:
        MagicMock: Мокированный объект TaskModel.
    """
    task = MagicMock(spec=TaskModel)
    task.id = uuid4()
    task.project_id = uuid4()
    task.parent_id = None
    task.team_id = uuid4()
    task.priority = "high"
    return task


@pytest.fixture
def mock_parent_task() -> MagicMock:
    """
    Создает мок родительской задачи.
    
    Возвращает:
        MagicMock: Мокированный объект TaskModel.
    """
    parent_task = MagicMock(spec=TaskModel)
    parent_task.id = uuid4()
    return parent_task


@pytest.fixture
def task_repo(mock_session) -> TaskRepository:
    """
    Создает экземпляр TaskRepository с моковой сессией.
    
    Args:
        mock_session: Мокированная сессия.
        
    Returns:
        TaskRepository: Экземпляр репозитория.
    """
    return TaskRepository(session=mock_session)


class TestTaskRepository:
    """Тесты для TaskRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        task_repo: TaskRepository,
        mock_task: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает задачу при успешном поиске по ID.
        
        Arrange: Мокируем session.get для возврата задачи.
        Act: Вызов get_by_id.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        task_id = mock_task.id
        mock_session.get.return_value = mock_task

        # Act
        result = await task_repo.get_by_id(task_id)

        # Assert
        mock_session.get.assert_called_once_with(TaskModel, task_id)
        assert result == mock_task

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        task_repo: TaskRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает None, если задача не найдена.
        
        Arrange: Мокируем session.get для возврата None.
        Act: Вызов get_by_id.
        Assert: Результат равен None.
        """
        # Arrange
        task_id = uuid4()
        mock_session.get.return_value = None

        # Act
        result = await task_repo.get_by_id(task_id)

        # Assert
        mock_session.get.assert_called_once_with(TaskModel, task_id)
        assert result is None


    @pytest.mark.asyncio
    async def test_get_by_user_id_success(
        self,
        task_repo: TaskRepository,
        mock_task: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_user_id возвращает задачи исполнителя.
        
        Arrange: Мокируем результат scalars.unique().all().
        Act: Вызов get_by_user_id.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        user_id = uuid4()
        mock_scalar_result = MagicMock()
        mock_scalar_result.unique.return_value.all.return_value = [mock_task]
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        tasks = await task_repo.get_by_user_id(user_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert len(tasks) == 1
        assert tasks[0] == mock_task

    @pytest.mark.asyncio
    async def test_get_sub_tasks_success(
        self,
        task_repo: TaskRepository,
        mock_task: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_sub_tasks возвращает подзадачи родительской задачи.
        
        Arrange: Мокируем результат scalars.unique().all().
        Act: Вызов get_sub_tasks.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        parent_id = mock_task.parent_id or uuid4() # Используем существующий parent_id или генерируем новый
        # Убедимся, что mock_task.parent_id равен parent_id для теста
        mock_task.parent_id = parent_id
        
        mock_scalar_result = MagicMock()
        mock_scalar_result.unique.return_value.all.return_value = [mock_task]
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        sub_tasks = await task_repo.get_sub_tasks(parent_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert len(sub_tasks) == 1
        assert sub_tasks[0] == mock_task

    @pytest.mark.asyncio
    async def test_get_parent_task_success(
        self,
        task_repo: TaskRepository,
        mock_task: MagicMock,
        mock_parent_task: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_parent_task возвращает родительскую задачу.
        
        Arrange: Мокируем результат scalars.first().
        Act: Вызов get_parent_task.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        task_id = mock_task.id
        mock_scalar_result = MagicMock()
        mock_scalar_result.first.return_value = mock_parent_task
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        parent = await task_repo.get_parent_task(task_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert parent == mock_parent_task

    @pytest.mark.asyncio
    async def test_get_parent_task_not_found(
        self,
        task_repo: TaskRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_parent_task возвращает None, если родительская задача не найдена.
        
        Arrange: Мокируем результат scalars.first() для возврата None.
        Act: Вызов get_parent_task.
        Assert: Результат равен None.
        """
        # Arrange
        task_id = uuid4()
        mock_scalar_result = MagicMock()
        mock_scalar_result.first.return_value = None
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        parent = await task_repo.get_parent_task(task_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert parent is None
