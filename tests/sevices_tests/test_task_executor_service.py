import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from typing import List, Tuple, Sequence

from app.src.api.services.task_executor_service import TaskExecutorService
from app.src.api.exceptions import TaskNotFound, UserNotFound
from app.src.api.shems import TaskExecutorOutSheme
from app.src.dal.database.models import TaskExecutorModel, UserModel, TaskModel
from app.src.dal.database.repositories import TaskRepository, TaskExecutorRepository


# --- Хелперы для создания моков ---

def create_mock_task(task_id: UUID | None = None, name: str = "Test Task") -> TaskModel:
    """Создает мок TaskModel."""
    task_id = task_id or uuid4()
    task = MagicMock(spec=TaskModel)
    task.id = task_id
    task.name = name
    task._sa_instance_state = MagicMock()
    return task

def create_mock_user(user_id: UUID | None = None, username: str = "test_user") -> UserModel:
    """Создает мок UserModel."""
    user_id = user_id or uuid4()
    user = MagicMock(spec=UserModel)
    user.id = user_id
    user.username = username
    user._sa_instance_state = MagicMock()
    return user

def create_mock_executor(
    task_id: UUID, 
    user_id: UUID, 
    estimate: int | None = None
) -> TaskExecutorModel:
    """Создает мок TaskExecutorModel."""
    executor = MagicMock(spec=TaskExecutorModel)
    executor.task_id = task_id
    executor.user_id = user_id
    executor.estimate = estimate
    executor._sa_instance_state = MagicMock()
    return executor


# --- Фикстуры ---

@pytest.fixture
def task_executor_service() -> TaskExecutorService:
    """Создает экземпляр TaskExecutorService."""
    return TaskExecutorService()

@pytest.fixture
def mock_task_repo() -> AsyncMock:
    """Создает моковый TaskRepository."""
    repo = AsyncMock(spec=TaskRepository)
    return repo

@pytest.fixture
def mock_task_executor_repo() -> AsyncMock:
    """Создает моковый TaskExecutorRepository."""
    repo = AsyncMock(spec=TaskExecutorRepository)
    return repo


class TestTaskExecutorService:
    """Тесты для TaskExecutorService."""

    # --- Тесты для add_executor ---

    @pytest.mark.asyncio
    async def test_add_executor_success(
        self, 
        task_executor_service, 
        mock_task_repo, 
        mock_task_executor_repo
    ):
        """Тест успешного добавления исполнителя."""
        task_id = uuid4()
        user_id = uuid4()
        estimate = 5
        
        # Мокируем задачу
        mock_task = create_mock_task(task_id)
        mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
        
        # Мокируем пользователя через публичный метод репозитория
        mock_user = create_mock_user(user_id)
        mock_task_executor_repo.get_by_id = AsyncMock(return_value=mock_user)
        
        # Мокируем проверку существования связки
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=None)
        
        # Мокируем создание
        mock_executor_model = create_mock_executor(task_id, user_id, estimate)
        mock_task_executor_repo.create = AsyncMock(return_value=mock_executor_model)

        result = await task_executor_service.add_executor(
            task_repo=mock_task_repo,
            task_executor_repo=mock_task_executor_repo,
            task_id=task_id,
            user_id=user_id,
            estimate=estimate
        )

        assert result is not None
        assert isinstance(result, TaskExecutorOutSheme)
        assert result.task_id == task_id
        assert result.user_id == user_id
        assert result.estimate == estimate
        
        # Проверка вызовов
        mock_task_repo.get_by_id.assert_called_once_with(task_id)
        mock_task_executor_repo.get_by_id.assert_called_once_with(user_id)
        mock_task_executor_repo.get_by_task_and_user.assert_called_once_with(task_id, user_id)
        mock_task_executor_repo.create.assert_called_once()
    @pytest.mark.asyncio
    async def test_add_executor_task_not_found(
        self, 
        task_executor_service, 
        mock_task_repo, 
        mock_task_executor_repo
    ):
        """Тест добавления исполнителя в несуществующую задачу."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_task_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TaskNotFound):
            await task_executor_service.add_executor(
                task_repo=mock_task_repo,
                task_executor_repo=mock_task_executor_repo,
                task_id=task_id,
                user_id=user_id
            )

    @pytest.mark.asyncio
    async def test_add_executor_user_not_found(
        self, 
        task_executor_service, 
        mock_task_repo, 
        mock_task_executor_repo
    ):
        """Тест добавления несуществующего пользователя."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_task = create_mock_task(task_id)
        mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
        
        # Пользователь не найден
        mock_task_executor_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(UserNotFound):
            await task_executor_service.add_executor(
                task_repo=mock_task_repo,
                task_executor_repo=mock_task_executor_repo,
                task_id=task_id,
                user_id=user_id
            )

    @pytest.mark.asyncio
    async def test_add_executor_already_exists(
        self, 
        task_executor_service, 
        mock_task_repo, 
        mock_task_executor_repo
    ):
        """Тест добавления уже существующего исполнителя."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_task = create_mock_task(task_id)
        mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
        
        mock_user = create_mock_user(user_id)
        mock_task_executor_repo.get_by_id = AsyncMock(return_value=mock_user)
        
        # Исполнитель уже есть
        existing_executor = create_mock_executor(task_id, user_id)
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=existing_executor)

        with pytest.raises(Exception, match="Исполнитель уже добавлен к задаче"):
            await task_executor_service.add_executor(
                task_repo=mock_task_repo,
                task_executor_repo=mock_task_executor_repo,
                task_id=task_id,
                user_id=user_id
            )

    # --- Тесты для remove_executor ---

    @pytest.mark.asyncio
    async def test_remove_executor_success(
        self, 
        task_executor_service, 
        mock_task_executor_repo
    ):
        """Тест успешного удаления исполнителя."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_executor = create_mock_executor(task_id, user_id)
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=mock_executor)
        mock_task_executor_repo.delete = AsyncMock()

        await task_executor_service.remove_executor(
            task_executor_repo=mock_task_executor_repo,
            task_id=task_id,
            user_id=user_id
        )

        mock_task_executor_repo.delete.assert_called_once_with(mock_executor)

    @pytest.mark.asyncio
    async def test_remove_executor_not_found(
        self, 
        task_executor_service, 
        mock_task_executor_repo
    ):
        """Тест удаления несуществующей связки."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="Связка задача-исполнитель не найдена"):
            await task_executor_service.remove_executor(
                task_executor_repo=mock_task_executor_repo,
                task_id=task_id,
                user_id=user_id
            )

    # --- Тесты для update_estimate ---

    @pytest.mark.asyncio
    async def test_update_estimate_success(
        self, 
        task_executor_service, 
        mock_task_executor_repo
    ):
        """Тест успешного обновления оценки."""
        task_id = uuid4()
        user_id = uuid4()
        new_estimate = 5
        
        mock_executor = create_mock_executor(task_id, user_id, estimate=3)
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=mock_executor)
        mock_task_executor_repo.update = AsyncMock()

        result = await task_executor_service.update_estimate(
            task_executor_repo=mock_task_executor_repo,
            task_id=task_id,
            user_id=user_id,
            estimate=new_estimate
        )

        assert result.estimate == new_estimate
        mock_task_executor_repo.update.assert_called_once_with(mock_executor)

    @pytest.mark.asyncio
    async def test_update_estimate_not_found(
        self, 
        task_executor_service, 
        mock_task_executor_repo
    ):
        """Тест обновления оценки несуществующей связки."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="Связка задача-исполнитель не найдена"):
            await task_executor_service.update_estimate(
                task_executor_repo=mock_task_executor_repo,
                task_id=task_id,
                user_id=user_id,
                estimate=5
            )

    # --- Тесты для get_executors_for_task ---

    @pytest.mark.asyncio
    async def test_get_executors_for_task_success(
        self, 
        task_executor_service, 
        mock_task_executor_repo
    ):
        """Тест получения списка исполнителей задачи."""
        task_id = uuid4()
        
        executor1 = create_mock_executor(task_id, uuid4())
        executor2 = create_mock_executor(task_id, uuid4())
        mock_executors = [executor1, executor2]
        
        mock_task_executor_repo.get_executors_for_task = AsyncMock(return_value=mock_executors)

        result = await task_executor_service.get_executors_for_task(
            task_executor_repo=mock_task_executor_repo,
            task_id=task_id
        )

        assert len(result) == 2
        assert all(isinstance(e, TaskExecutorOutSheme) for e in result)

    @pytest.mark.asyncio
    async def test_get_executors_for_task_empty(
        self, 
        task_executor_service, 
        mock_task_executor_repo
    ):
        """Тест получения пустого списка исполнителей."""
        task_id = uuid4()
        
        mock_task_executor_repo.get_executors_for_task = AsyncMock(return_value=[])

        result = await task_executor_service.get_executors_for_task(
            task_executor_repo=mock_task_executor_repo,
            task_id=task_id
        )

        assert result == []

    # --- Тесты для get_tasks_for_user ---

    @pytest.mark.asyncio
    async def test_get_tasks_for_user_success(
        self, 
        task_executor_service, 
        mock_task_executor_repo
    ):
        """Тест получения задач пользователя с пагинацией."""
        user_id = uuid4()
        
        task1 = create_mock_task(uuid4())
        task2 = create_mock_task(uuid4())
        mock_tasks = [task1, task2]
        total = 2
        
        # Метод репозитория возвращает кортеж (tasks, total)
        mock_task_executor_repo.get_tasks_for_user = AsyncMock(return_value=(mock_tasks, total))

        tasks, total_count = await task_executor_service.get_tasks_for_user(
            task_executor_repo=mock_task_executor_repo,
            user_id=user_id,
            page=1,
            page_size=10
        )

        assert len(tasks) == 2
        assert total_count == 2
        assert tasks[0].id == task1.id
        assert tasks[1].id == task2.id

    @pytest.mark.asyncio
    async def test_get_tasks_for_user_empty(
        self, 
        task_executor_service, 
        mock_task_executor_repo
    ):
        """Тест получения пустого списка задач."""
        user_id = uuid4()
        
        mock_task_executor_repo.get_tasks_for_user = AsyncMock(return_value=([], 0))

        tasks, total_count = await task_executor_service.get_tasks_for_user(
            task_executor_repo=mock_task_executor_repo,
            user_id=user_id
        )

        assert tasks == []
        assert total_count == 0