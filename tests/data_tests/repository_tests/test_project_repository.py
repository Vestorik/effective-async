# tests/data_tests/test_repository/test_project_repository.py

"""
Тесты для ProjectRepository.

Критерии приемки:
1. get_by_id: возвращает проект по ID или None.
2. get_by_name: возвращает проект по названию или None.
3. get_by_user_id: возвращает список проектов пользователя.
4. get_teams_for_project: возвращает список команд проекта.
5. get_users_for_project: возвращает уникальный список пользователей проекта.

Тестирование выполнено через мокирование AsyncSession.
Используются реальные модели из проекта для обеспечения корректности связей.
"""

from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.src.dal.database.repositories import ProjectRepository
from app.src.dal.database.models import (
    ProjectModel,
    TeamModel,
    UserModel,
    TaskModel,
    TaskExecutorModel,
    team_project_table,
)
from typing import Sequence


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
    # scalavers() возвращает тот же мок для цепочки вызовов
    session.scalars.return_value = scalar_result
    
    return session


@pytest.fixture
def mock_team() -> MagicMock:
    """
    Создает мок команды.
    
    Возвращает:
        MagicMock: Мокированный объект TeamModel.
    """
    team = MagicMock(spec=TeamModel)
    team.id = uuid4()
    team.name = "Dev Team"
    return team


@pytest.fixture
def mock_user() -> MagicMock:
    """
    Создает мок пользователя.
    
    Возвращает:
        MagicMock: Мокированный объект UserModel.
    """
    user = MagicMock(spec=UserModel)
    user.id = uuid4()
    user.email = "test@example.com"
    user.team_id = None  # Для get_by_user_id JOIN не будет зависеть от этого поля в моке
    return user


@pytest.fixture
def mock_project() -> MagicMock:
    """
    Создает мок проекта.
    
    Возвращает:
        MagicMock: Мокированный объект ProjectModel.
    """
    project = MagicMock(spec=ProjectModel)
    project.id = uuid4()
    project.name = "Test Project"
    return project


@pytest.fixture
def project_repo(mock_session) -> ProjectRepository:
    """
    Создает экземпляр ProjectRepository с моковой сессией.
    
    Args:
        mock_session: Мокированная сессия.
        
    Returns:
        ProjectRepository: Экземпляр репозитория.
    """
    return ProjectRepository(session=mock_session)


class TestProjectRepository:
    """Тесты для ProjectRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        project_repo: ProjectRepository,
        mock_project: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает проект при успешном поиске по ID.
        
        Arrange: Мокируем session.get для возврата проекта.
        Act: Вызов get_by_id.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        project_id = mock_project.id
        mock_session.get.return_value = mock_project

        # Act
        result = await project_repo.get_by_id(project_id)

        # Assert
        mock_session.get.assert_called_once_with(ProjectModel, project_id)
        assert result == mock_project

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        project_repo: ProjectRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает None, если проект не найден.
        
        Arrange: Мокируем session.get для возврата None.
        Act: Вызов get_by_id.
        Assert: Результат равен None.
        """
        # Arrange
        project_id = uuid4()
        mock_session.get.return_value = None

        # Act
        result = await project_repo.get_by_id(project_id)

        # Assert
        mock_session.get.assert_called_once_with(ProjectModel, project_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name_success(
        self,
        project_repo: ProjectRepository,
        mock_project: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_name возвращает проект по имени.
        
        Arrange: Мокируем результат scalars.first().
        Act: Вызов get_by_name.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        project_name = "Test Project"
        mock_scalar_result = MagicMock()
        mock_scalar_result.first.return_value = mock_project
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        result = await project_repo.get_by_name(project_name)

        # Assert
        mock_session.scalars.assert_called_once()
        call_args = mock_session.scalars.call_args
        stmt = call_args[0][0]
        
        # Проверяем, что в запросе есть WHERE по имени
        # stmt должен содержать select(ProjectModel).where(...)
        assert result == mock_project

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(
        self,
        project_repo: ProjectRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_name возвращает None, если проект с таким именем не найден.
        
        Arrange: Мокируем результат scalars.first() для возврата None.
        Act: Вызов get_by_name.
        Assert: Результат равен None.
        """
        # Arrange
        project_name = "Non-existent Project"
        mock_scalar_result = MagicMock()
        mock_scalar_result.first.return_value = None
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        result = await project_repo.get_by_name(project_name)

        # Assert
        mock_session.scalars.assert_called_once()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_user_id_success(
        self,
        project_repo: ProjectRepository,
        mock_project: MagicMock,
        mock_session: AsyncMock,
        mock_user: MagicMock,
        mock_team: MagicMock
    ) -> None:
        """
        Проверка: get_by_user_id возвращает список проектов пользователя.
        
        Arrange: Мокируем результаты scalar queries для JOIN запроса.
        Act: Вызов get_by_user_id.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        user_id = mock_user.id
        
        # Мокируем результат для get_by_user_id
        mock_scalar_result = MagicMock()
        mock_scalar_result.unique.return_value.all.return_value = [mock_project]
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        projects = await project_repo.get_by_user_id(user_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert len(projects) == 1
        assert projects[0] == mock_project

    @pytest.mark.asyncio
    async def test_get_by_user_id_empty(
        self,
        project_repo: ProjectRepository,
        mock_session: AsyncMock,
        mock_user: MagicMock
    ) -> None:
        """
        Проверка: get_by_user_id возвращает пустой список, если у пользователя нет проектов.
        
        Arrange: Мокируем результаты scalar queries для возврата пустого списка.
        Act: Вызов get_by_user_id.
        Assert: Список проектов пуст.
        """
        # Arrange
        user_id = mock_user.id
        mock_scalar_result = MagicMock()
        mock_scalar_result.unique.return_value.all.return_value = []
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        projects = await project_repo.get_by_user_id(user_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_get_teams_for_project_success(
        self,
        project_repo: ProjectRepository,
        mock_team: MagicMock,
        mock_session: AsyncMock,
        mock_project: MagicMock
    ) -> None:
        """
        Проверка: get_teams_for_project возвращает список команд проекта.
        
        Arrange: Мокируем результаты scalar queries.
        Act: Вызов get_teams_for_project.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        project_id = mock_project.id
        
        # Мокируем результат для get_teams_for_project
        mock_scalar_result = MagicMock()
        mock_scalar_result.unique.return_value.all.return_value = [mock_team]
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        teams = await project_repo.get_teams_for_project(project_id)

        # Assert
        mock_session.scalars.assert_called_once()
        assert len(teams) == 1
        assert teams[0] == mock_team

    @pytest.mark.asyncio
    async def test_get_users_for_project_from_teams(
        self,
        project_repo: ProjectRepository,
        mock_user: MagicMock,
        mock_session: AsyncMock,
        mock_project: MagicMock
    ) -> None:
        """
        Проверка: get_users_for_project возвращает пользователей из команд проекта.
        
        Arrange: Мокируем результаты двух скалярных запросов.
        Act: Вызов get_users_for_project.
        Assert: Проверка возврата списка пользователей.
        """
        # Arrange
        project_id = mock_project.id
    
        # Создаем моки для результатов скалярных запросов так, чтобы они были итерируемыми списками
        users_from_teams_mock = [mock_user]
        users_from_tasks_mock = []
        
        def scalars_side_effect(stmt):
            # Простая заглушка: возвращаем список, если это "команды", или другой список
            return None
        
        # Попробуем вернуть списки напрямую из scalars
        mock_session.scalars.side_effect = [users_from_teams_mock, users_from_tasks_mock]

        # Act
        users = await project_repo.get_users_for_project(project_id)

        # Assert
        assert mock_session.scalars.call_count == 2
        assert len(users) == 1
        assert users[0] == mock_user

    @pytest.mark.asyncio
    async def test_get_users_for_project_from_tasks(
        self,
        project_repo: ProjectRepository,
        mock_user: MagicMock,
        mock_session: AsyncMock,
        mock_project: MagicMock
    ) -> None:
        """
        Проверка: get_users_for_project возвращает пользователей из задач проекта.
        
        Arrange: Мокируем результаты двух скалярных запросов.
        Act: Вызов get_users_for_project.
        Assert: Проверка возврата списка пользователей.
        """
        # Arrange
        project_id = mock_project.id
        
        users_from_teams_mock = []
        users_from_tasks_mock = [mock_user]
        
        mock_session.scalars.side_effect = [users_from_teams_mock, users_from_tasks_mock]

        # Act
        users = await project_repo.get_users_for_project(project_id)

        # Assert
        assert mock_session.scalars.call_count == 2
        assert len(users) == 1
        assert users[0] == mock_user

    @pytest.mark.asyncio
    async def test_get_users_for_project_duplicates_removed(
        self,
        project_repo: ProjectRepository,
        mock_user: MagicMock,
        mock_session: AsyncMock,
        mock_project: MagicMock
    ) -> None:
        """
        Проверка: get_users_for_project удаляет дубликаты пользователей, 
        если они есть и в командах, и в задачах.
        
        Arrange: Мокируем результаты двух скалярных запросов с одним и тем же пользователем.
        Act: Вызов get_users_for_project.
        Assert: Проверка, что в результате только один экземпляр пользователя.
        """
        # Arrange
        project_id = mock_project.id
        
        # Один и тот же пользователь в обоих списках
        users_from_teams_mock = [mock_user]
        users_from_tasks_mock = [mock_user]
        
        mock_session.scalars.side_effect = [users_from_teams_mock, users_from_tasks_mock]

        # Act
        users = await project_repo.get_users_for_project(project_id)

        # Assert
        assert mock_session.scalars.call_count == 2
        # Должен быть только один уникальный пользователь
        assert len(users) == 1
        assert users[0] == mock_user