import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timezone
from typing import List

from app.src.api.services.project_service import ProjectService
from app.src.api.exceptions import ProjectNotFound
from app.src.api.shems import ProjectSchema
from app.src.dal.database.models import ProjectModel, TeamModel
from app.src.dal.database.repositories import ProjectRepository, TeamRepository


# Фикстуры для моков
@pytest.fixture
def mock_project_repo():
    repo = AsyncMock(spec=ProjectRepository)
    return repo


@pytest.fixture
def mock_team_repo():
    repo = AsyncMock(spec=TeamRepository)
    return repo


@pytest.fixture
def project_service():
    return ProjectService()


# Хелперы для создания моков моделей
def create_mock_project(project_id: UUID | None= None, name: str = "Test Project", description: str = "Test Desc", team_ids: list | None= None) -> ProjectModel:
    """Создает мок ProjectModel."""
    project_id = project_id or uuid4()

    project = MagicMock()
    project.id = project_id
    project.name = name
    project.description = description
    project.project_teams = []
    project.updated_at = None
    project._sa_instance_state = MagicMock()
    return project


def create_mock_team(team_id: UUID | None = None, name: str = "Test Team") -> TeamModel:
    """Создает мок TeamModel."""
    team_id = team_id or uuid4()
    team = MagicMock()
    team.id = team_id
    team.name = name
    # Явно добавляем атрибут, который SQLAlchemy ожидает увидеть у ORM-объектов
    team._sa_instance_state = MagicMock()
    return team


class TestProjectService:
    """Тесты для ProjectService."""

    @pytest.mark.asyncio
    async def test_create_project_success(self, project_service, mock_project_repo, mock_team_repo):
        """Тест успешного создания проекта."""
        project_id = uuid4()
        team_id = uuid4()
        team = create_mock_team(team_id)
        
        # Настраиваем моки репозиториев
        mock_project_repo.get_by_name = AsyncMock(return_value=None)  # Проект не существует
        mock_project_repo.create = AsyncMock()  # Создаем проект
        mock_project_repo.update = AsyncMock()  # Обновляем проект для привязки команд
        
        # Мокаем team_repo для проверки существования команд
        mock_team_repo.get_by_id = AsyncMock(return_value=team)
        
        # Вызываем сервис
        # Поскольку сервис создает новый объект ProjectModel, мы не можем напрямую проверить
        # изменения в mock_project, если он не тот же экземпляр.
        # Вместо этого мы проверим корректность вызовов репозиториев.
        
        result = await project_service.create_project(
            project_repo=mock_project_repo,
            team_repo=mock_team_repo,
            name="New Project",
            description="New Desc",
            team_ids=[team_id]
        )
        
        # Проверки
        assert result is not None
        assert isinstance(result, ProjectSchema)
        assert result.name == "New Project"
        
        # Проверяем, что репозитории были вызваны корректно
        mock_project_repo.get_by_name.assert_called_once_with("New Project")
        # create вызывается с новым объектом
        mock_project_repo.create.assert_called_once()
        
        # Проверяем, что для каждой указанной команды был выполнен запрос get_by_id
        mock_team_repo.get_by_id.assert_called_once_with(team_id)
        
        # update вызывается после создания и привязки команд
        mock_project_repo.update.assert_called_once()
        
        # Дополнительно: можно проверить, что create был вызван с объектом, имеющим правильные атрибуты
        call_args = mock_project_repo.create.call_args
        created_project = call_args[0][0]
        assert created_project.name == "New Project"
        assert created_project.description == "New Desc"

    @pytest.mark.asyncio
    async def test_create_project_duplicate_name(self, project_service, mock_project_repo, mock_team_repo):
        """Тест создания проекта с существующим названием."""
        mock_project_repo.get_by_name = AsyncMock(return_value=create_mock_project())  # Проект уже существует
        
        with pytest.raises(Exception, match="Проект с названием .* уже существует"):
            await project_service.create_project(
                project_repo=mock_project_repo,
                team_repo=mock_team_repo,
                name="Existing Project",
                description="Desc"
            )

    @pytest.mark.asyncio
    async def test_create_project_invalid_team(self, project_service, mock_project_repo, mock_team_repo):
        """Тест создания проекта с несуществующей командой."""
        team_id = uuid4()
        mock_project_repo.get_by_name = AsyncMock(return_value=None)
        mock_project_repo.create = AsyncMock()
        mock_team_repo.get_by_id = AsyncMock(return_value=None)  # Команда не найдена
        
        with pytest.raises(Exception, match="Команда с ID .* не найдена"):
            await project_service.create_project(
                project_repo=mock_project_repo,
                team_repo=mock_team_repo,
                name="New Project",
                description="Desc",
                team_ids=[team_id]
            )

    @pytest.mark.asyncio
    async def test_get_project_by_id_success(self, project_service, mock_project_repo):
        """Тест успешного получения проекта по ID."""
        project_id = uuid4()
        mock_project = create_mock_project(project_id)
        mock_project_repo.get_by_id = AsyncMock(return_value=mock_project)
        
        result = await project_service.get_project_by_id(
            project_repo=mock_project_repo,
            project_id=project_id
        )
        
        assert result is not None
        assert isinstance(result, ProjectSchema)
        assert result.id == project_id
  

    @pytest.mark.asyncio
    async def test_get_project_by_id_not_found(self, project_service, mock_project_repo):
        """Тест получения несуществующего проекта."""
        project_id = uuid4()
        mock_project_repo.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ProjectNotFound):
            await project_service.get_project_by_id(
                project_repo=mock_project_repo,
                project_id=project_id
            )

    @pytest.mark.asyncio
    async def test_get_projects_for_team_success(self, project_service, mock_project_repo):
        """Тест получения проектов команды."""
        team_id = uuid4()
        mock_project1 = create_mock_project(project_id=uuid4(), name="Proj 1")
        mock_project2 = create_mock_project(project_id=uuid4(), name="Proj 2")
        
        mock_project_repo.get_teams_for_project = AsyncMock(return_value=[mock_project1, mock_project2])
        
        result = await project_service.get_projects_for_team(
            project_repo=mock_project_repo,
            team_id=team_id
        )
        
        assert len(result) == 2
        assert all(isinstance(p, ProjectSchema) for p in result)
        assert result[0].name == "Proj 1"
        assert result[1].name == "Proj 2"

    @pytest.mark.asyncio
    async def test_get_projects_for_user_success(self, project_service, mock_project_repo):
        """Тест получения проектов пользователя."""
        user_id = uuid4()
        mock_project1 = create_mock_project(project_id=uuid4(), name="User Proj 1")
        mock_project2 = create_mock_project(project_id=uuid4(), name="User Proj 2")
        
        mock_project_repo.get_by_user_id = AsyncMock(return_value=[mock_project1, mock_project2])
        
        result = await project_service.get_projects_for_user(
            project_repo=mock_project_repo,
            user_id=user_id
        )
        
        assert len(result) == 2
        assert all(isinstance(p, ProjectSchema) for p in result)



    @pytest.mark.asyncio
    async def test_update_project_not_found(self, project_service, mock_project_repo):
        """Тест обновления несуществующего проекта."""
        project_id = uuid4()
        mock_project_repo.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ProjectNotFound):
            await project_service.update_project(
                project_repo=mock_project_repo,
                project_id=project_id,
                name="Updated Name"
            )


    @pytest.mark.asyncio
    async def test_delete_project_success(self, project_service, mock_project_repo):
        """Тест успешного удаления проекта."""
        project_id = uuid4()
        mock_project = create_mock_project(project_id)
        
        mock_project_repo.get_by_id = AsyncMock(return_value=mock_project)
        mock_project_repo.delete = AsyncMock()
        
        await project_service.delete_project(
            project_repo=mock_project_repo,
            project_id=project_id
        )
        
        mock_project_repo.delete.assert_called_once_with(mock_project)

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, project_service, mock_project_repo):
        """Тест удаления несуществующего проекта."""
        project_id = uuid4()
        mock_project_repo.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ProjectNotFound):
            await project_service.delete_project(
                project_repo=mock_project_repo,
                project_id=project_id
            )