import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from uuid import uuid4, UUID
from typing import Optional, Sequence
from datetime import datetime

from app.src.api.services.task_service import TaskService
from app.src.api.exceptions import TaskNotFound, TeamNotFound
from app.src.dal.database.repositories import TaskRepository, TaskExecutorRepository, TeamRepository
from app.src.dal.database.models import TaskModel, TaskExecutorModel, TeamModel


# --- Хелперы для создания моков ---

def create_mock_task(
    task_id: Optional[UUID] = None,
    name: str = "Test Task",
    description: Optional[str] = None,
    priority: str = "medium",
    team_id: Optional[UUID] = None,
    parent_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None
) -> TaskModel:
    """Создает мок TaskModel."""
    task = MagicMock(spec=TaskModel)
    task.id = task_id or uuid4()
    task.name = name
    task.description = description
    task.priority = priority
    task.team_id = team_id
    task.parent_id = parent_id
    task.project_id = project_id
    task.created_at = created_at or datetime.now()
    task.updated_at = updated_at or datetime.now()
    # SQLAlchemy требует наличия _sa_instance_state для работы с ORM-моками
    task._sa_instance_state = MagicMock()
    return task


def create_mock_team(team_id: Optional[UUID] = None, name: str = "Test Team") -> TeamModel:
    """Создает мок TeamModel."""
    team = MagicMock(spec=TeamModel)
    team.id = team_id or uuid4()
    team.name = name
    return team


def create_mock_executor(
    task_id: UUID,
    user_id: UUID,
    estimate: Optional[int] = None
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
def task_service() -> TaskService:
    """Создает экземпляр TaskService."""
    return TaskService()


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


@pytest.fixture
def mock_team_repo() -> AsyncMock:
    """Создает моковый TeamRepository."""
    repo = AsyncMock(spec=TeamRepository)
    return repo


class TestTaskService:
    """Тесты для TaskService."""

    # --- Тесты для create_task ---

    @pytest.mark.asyncio
    async def test_create_task_success(self, task_service, mock_task_repo, mock_task_executor_repo, mock_team_repo):
        """Тест успешного создания задачи с исполнителями."""
        team_id = uuid4()
        user_id = uuid4()
        executor_id = uuid4()
        task_name = "New Task"
        
        team = create_mock_team(team_id)
        mock_task_repo.get_by_name = AsyncMock(return_value=None) # Проверка дубликатов, если есть в другом месте, но здесь валидация команды
        mock_team_repo.get_by_id = AsyncMock(return_value=team)
        
        # Мокируем создание задачи
        mock_task = create_mock_task(team_id=team_id)
        mock_task_repo.create = AsyncMock(return_value=mock_task) # create часто возвращает сохраненный объект
        
        # Мокируем создание исполнителей
        mock_task_executor_repo.create = AsyncMock()

        result = await task_service.create_task(
            task_repo=mock_task_repo,
            task_executor_repo=mock_task_executor_repo,
            team_repo=mock_team_repo,
            user_id=user_id,
            team_id=team_id,
            name=task_name,
            description="Task Desc",
            priority="high",
            executor_ids=[executor_id]
        )

        # Проверки
        assert result is not None
        assert isinstance(result, TaskModel)
        assert result.name == task_name
        assert result.team_id == team_id
        
        # Проверка вызовов репозиториев
        mock_team_repo.get_by_id.assert_called_once_with(team_id)
        mock_task_repo.create.assert_called_once()
        mock_task_executor_repo.create.assert_called_once_with(
            ANY
        )
        
        # Проверка, что executor был создан с правильными ID
        call_args = mock_task_executor_repo.create.call_args
        executor_arg = call_args[0][0]
        assert executor_arg.user_id == executor_id
        assert executor_arg.task_id == result.id

    @pytest.mark.asyncio
    async def test_create_task_team_not_found(self, task_service, mock_task_repo, mock_task_executor_repo, mock_team_repo):
        """Тест создания задачи с несуществующей командой."""
        team_id = uuid4()
        
        mock_team_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TeamNotFound):
            await task_service.create_task(
                task_repo=mock_task_repo,
                task_executor_repo=mock_task_executor_repo,
                team_repo=mock_team_repo,
                user_id=uuid4(),
                team_id=team_id,
                name="Task"
            )

    @pytest.mark.asyncio
    async def test_create_task_invalid_parent(self, task_service, mock_task_repo, mock_task_executor_repo, mock_team_repo):
        """Тест создания подзадачи с неверным parent_id (project_id у родителя)."""
        team_id = uuid4()
        parent_id = uuid4()
        
        mock_team_repo.get_by_id = AsyncMock(return_value=create_mock_team(team_id))
        mock_task_repo.get_by_id = AsyncMock(return_value=create_mock_task(parent_id, project_id=uuid4())) # Родитель является проектом или ошибкой

        with pytest.raises(Exception, match="Родительская задача не найдена или неверная структура"):
            await task_service.create_task(
                task_repo=mock_task_repo,
                task_executor_repo=mock_task_executor_repo,
                team_repo=mock_team_repo,
                user_id=uuid4(),
                team_id=team_id,
                name="Subtask",
                parent_id=parent_id
            )

    @pytest.mark.asyncio
    async def test_create_task_no_executors(self, task_service, mock_task_repo, mock_task_executor_repo, mock_team_repo):
        """Тест создания задачи без исполнителей."""
        team_id = uuid4()
        
        mock_team_repo.get_by_id = AsyncMock(return_value=create_mock_team(team_id))
        mock_task_repo.create = AsyncMock(return_value=create_mock_task(team_id=team_id))

        await task_service.create_task(
            task_repo=mock_task_repo,
            task_executor_repo=mock_task_executor_repo,
            team_repo=mock_team_repo,
            user_id=uuid4(),
            team_id=team_id,
            name="Task No Execs",
            executor_ids=None
        )

        # Исполнитель не должен быть создан
        mock_task_executor_repo.create.assert_not_called()

    # --- Тесты для list_tasks ---

    @pytest.mark.asyncio
    async def test_list_tasks_success(self, task_service, mock_task_repo):
        """Тест успешного получения списка задач."""
        team_id = uuid4()
        mock_tasks = [
            create_mock_task(team_id=team_id, name="Task 1"),
            create_mock_task(team_id=team_id, name="Task 2")
        ]
        mock_task_repo.get_tasks_by_team_and_priority = AsyncMock(return_value=mock_tasks)

        result = await task_service.list_tasks(
            task_repo=mock_task_repo,
            team_id=team_id,
            priority="high"
        )

        assert len(result) == 2
        assert result[0].name == "Task 1"
        mock_task_repo.get_tasks_by_team_and_priority.assert_called_once_with(team_id, "high")

    @pytest.mark.asyncio
    async def test_list_tasks_no_filter(self, task_service, mock_task_repo):
        """Тест получения всех задач команды."""
        team_id = uuid4()
        mock_task_repo.get_tasks_by_team_and_priority = AsyncMock(return_value=[])

        result = await task_service.list_tasks(
            task_repo=mock_task_repo,
            team_id=team_id
        )

        assert result == []
        mock_task_repo.get_tasks_by_team_and_priority.assert_called_once_with(team_id, None)

    # --- Тесты для update_task ---

    @pytest.mark.asyncio
    async def test_update_task_success(self, task_service, mock_task_repo):
        """Тест успешного обновления задачи."""
        task_id = uuid4()
        mock_task = create_mock_task(task_id, name="Old Name")
        
        mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_task_repo.update = AsyncMock()

        result = await task_service.update_task(
            task_repo=mock_task_repo,
            task_id=task_id,
            name="New Name"
        )

        assert result.name == "New Name"
        assert result.id == task_id
        mock_task_repo.update.assert_called_once_with(mock_task)

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, task_service, mock_task_repo):
        """Тест обновления несуществующей задачи."""
        task_id = uuid4()
        
        mock_task_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TaskNotFound):
            await task_service.update_task(
                task_repo=mock_task_repo,
                task_id=task_id,
                name="New Name"
            )

    @pytest.mark.asyncio
    async def test_update_task_partial_update(self, task_service, mock_task_repo):
        """Тест обновления только описания."""
        task_id = uuid4()
        mock_task = create_mock_task(task_id, name="Name", description="Desc")
        
        mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_task_repo.update = AsyncMock()

        await task_service.update_task(
            task_repo=mock_task_repo,
            task_id=task_id,
            description="Updated Desc"
        )

        assert mock_task.name == "Name" # Имя не изменилось
        assert mock_task.description == "Updated Desc"
        mock_task_repo.update.assert_called_once()

    # --- Тесты для delete_task ---

    @pytest.mark.asyncio
    async def test_delete_task_success(self, task_service, mock_task_repo):
        """Тест успешного удаления задачи."""
        task_id = uuid4()
        mock_task = create_mock_task(task_id)
        
        mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_task_repo.delete = AsyncMock()

        await task_service.delete_task(
            task_repo=mock_task_repo,
            task_id=task_id
        )

        mock_task_repo.delete.assert_called_once_with(mock_task)

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, task_service, mock_task_repo):
        """Тест удаления несуществующей задачи."""
        task_id = uuid4()
        
        mock_task_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TaskNotFound):
            await task_service.delete_task(
                task_repo=mock_task_repo,
                task_id=task_id
            )

    # --- Тесты для add_executor ---

    @pytest.mark.asyncio
    async def test_add_executor_success(self, task_service, mock_task_repo, mock_task_executor_repo):
        """Тест успешного добавления исполнителя."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_task = create_mock_task(task_id)
        mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
        
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=None) # Не существует
        mock_task_executor_repo.create = AsyncMock()

        result = await task_service.add_executor(
            task_repo=mock_task_repo,
            task_executor_repo=mock_task_executor_repo,
            task_id=task_id,
            user_id=user_id,
            estimate=5
        )

        assert result.user_id == user_id
        assert result.task_id == task_id
        assert result.estimate == 5
        mock_task_executor_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_executor_already_exists(self, task_service, mock_task_repo, mock_task_executor_repo):
        """Тест добавления существующего исполнителя."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_task = create_mock_task(task_id)
        mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
        
        existing_executor = create_mock_executor(task_id, user_id)
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=existing_executor)

        with pytest.raises(Exception, match="Исполнитель уже добавлен к задаче"):
            await task_service.add_executor(
                task_repo=mock_task_repo,
                task_executor_repo=mock_task_executor_repo,
                task_id=task_id,
                user_id=user_id
            )

    @pytest.mark.asyncio
    async def test_add_executor_task_not_found(self, task_service, mock_task_repo, mock_task_executor_repo):
        """Тест добавления исполнителя в несуществующую задачу."""
        task_id = uuid4()
        
        mock_task_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TaskNotFound):
            await task_service.add_executor(
                task_repo=mock_task_repo,
                task_executor_repo=mock_task_executor_repo,
                task_id=task_id,
                user_id=uuid4()
            )

    # --- Тесты для update_executor_estimate ---

    @pytest.mark.asyncio
    async def test_update_executor_estimate_success(self, task_service, mock_task_executor_repo):
        """Тест успешного обновления оценки."""
        task_id = uuid4()
        user_id = uuid4()
        
        existing_executor = create_mock_executor(task_id, user_id, estimate=3)
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=existing_executor)
        mock_task_executor_repo.update = AsyncMock()

        result = await task_service.update_executor_estimate(
            task_executor_repo=mock_task_executor_repo,
            task_id=task_id,
            user_id=user_id,
            estimate=5
        )

        assert result.estimate == 5
        mock_task_executor_repo.update.assert_called_once_with(existing_executor)

    @pytest.mark.asyncio
    async def test_update_executor_estimate_not_found(self, task_service, mock_task_executor_repo):
        """Тест обновления оценки несуществующей связки."""
        task_id = uuid4()
        user_id = uuid4()
        
        mock_task_executor_repo.get_by_task_and_user = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="Связка задача-исполнитель не найдена"):
            await task_service.update_executor_estimate(
                task_executor_repo=mock_task_executor_repo,
                task_id=task_id,
                user_id=user_id,
                estimate=5
            )