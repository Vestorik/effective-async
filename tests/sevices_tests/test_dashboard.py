import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime
from typing import Sequence

# Импортируем сущности из приложения
from app.src.api.services.dashboard_service import DashboardService
from app.src.dal.database.models import TeamModel, ProjectModel, TaskModel, TaskExecutorModel, UserModel
from app.src.dal.database.repositories import TeamRepository
from app.src.api.shems import (
    TeamWithProjectsOutSheme,
    ProjectWithTasksOutSheme,
    TaskWithExecutorsOutSheme
)        # Импортируем модуль сервиса для патчинга
import app.src.api.services.dashboard_service as dash_module
import app.src.api.services.dashboard_service as dash_module
from unittest.mock import patch, MagicMock

# --- Фикстуры для создания моковых объектов ORM ---

def create_mock_user(user_id=None, team_id=None):
    """Создает мок UserModel."""
    user_id = user_id or uuid4()
    user = MagicMock(spec=UserModel)
    user.id = user_id
    user.username = f"user_{user_id}"
    user.team_id = team_id
    return user


def create_mock_task(task_id=None, name="Task Name", project_id=None):
    """Создает мок TaskModel."""
    task_id = task_id or uuid4()
    task = MagicMock(spec=TaskModel)
    task.id = task_id
    task.name = name
    task.description = f"Description for {name}"
    task.project_id = project_id
    task.executors = []  # Исполнители будут добавляться отдельно
    return task


def create_mock_executor(executor_id=None, name="Executor Name", task_id=None, user_id=None):
    """Создает мок TaskExecutorModel."""
    executor_id = executor_id or uuid4()
    #task_id и user_id должны быть валидными UUID, даже если они "моковые", так как они нужны для валидации схем
    task_id_val = task_id or uuid4() 
    user_id_val = user_id or uuid4()
    
    executor = MagicMock(spec=TaskExecutorModel)
    executor.id = executor_id
    executor.name = name
    executor.task_id = task_id_val
    executor.user_id = user_id_val
    return executor



def create_mock_project(project_id=None, name="Project Name", team_id=None):
    """Создает мок ProjectModel."""
    project_id = project_id or uuid4()
    project = MagicMock(spec=ProjectModel)
    project.id = project_id
    project.name = name
    project.description = f"Description for {name}"
    project.team_id = team_id
    project.project_tasks = []  # Задачи будут добавляться отдельно
    return project


def create_mock_team(team_id=None, name="Team Name"):
    """Создает мок TeamModel."""
    team_id = team_id or uuid4()
    team = MagicMock(spec=TeamModel)
    team.id = team_id
    team.name = name
    team.users = []  # Пользователи будут добавляться отдельно
    team.team_projects = []  # Проекты будут добавляться отдельно
    return team


# --- Фикстура сессии и репозиториев ---

@pytest.fixture
def mock_session():
    """Создает мок AsyncSession."""
    session = AsyncMock()
    # Мокаем execute для глобального запроса проектов
    session.execute = AsyncMock()
    return session


@pytest.fixture
def dashboard_service(mock_session):
    """Создает экземпляр DashboardService с моковой сессией."""
    return DashboardService(session=mock_session)


class TestDashboardService:
    """Тесты для класса DashboardService."""

    @pytest.mark.asyncio
    async def test_get_dashboard_data_with_teams_and_projects(self, mock_session):
        """
        Тест получения данных дашборда с командами, проектами, задачами и исполнителями.
        """
        # Создаем структуру данных
        user1 = create_mock_user()
        user2 = create_mock_user()
        
        task1 = create_mock_task()
        task2 = create_mock_task()
        
        executor1 = create_mock_executor()
        executor2 = create_mock_executor()
        
        task1.executors = [executor1, executor2]
        task2.executors = []
        
        project1 = create_mock_project()
        project1.project_tasks = [task1, task2]
        
        team1 = create_mock_team()
        team1.users = [user1, user2]
        team1.team_projects = [project1]
        
        # --- Мокаем TeamRepository ---
        # Создаем моковый экземпляр репозитория
        team_repo_mock = MagicMock(spec=TeamRepository)
        team_repo_mock.get_all = AsyncMock(return_value=[team1])
        team_repo_mock.get_team_with_projects = AsyncMock(return_value=team1)
        
        # Переопределяем поведение внутри сервиса, чтобы вернуть наш моковый репозиторий
        # Вместо создания реального экземпляра, мы патчим класс или метод инициализации
        # В данном случае, так как TeamRepository создается внутри метода, мы можем использовать patch
        

        
        with patch.object(dash_module, 'TeamRepository', return_value=team_repo_mock):
            service = DashboardService(session=mock_session)
            
           # --- Мокаем глобальный запрос проектов (session.execute) ---
            # Имитируем результат selectinload
            # Создаем мок результата запроса
            # .scalars() и .unique() должны быть синхронными, поэтому используем MagicMock
            scalars_mock = MagicMock()
            unique_mock = MagicMock()
            scalars_mock.unique = MagicMock(return_value=unique_mock)
            unique_mock.all.return_value = [project1]
            
            mock_result = AsyncMock()
            # Явно задаем scalars как MagicMock, чтобы он не возвращал coroutine
            mock_result.scalars = MagicMock(return_value=scalars_mock)
            
            mock_session.execute.return_value = mock_result
            
            user_id = user1.id
            result = await service.get_dashboard_data(user_id)
            
            # Проверки
            assert "teams" in result
            assert "projects" in result
            assert len(result["teams"]) == 1
            assert len(result["projects"]) == 1
            
            # Проверка структуры команды
            team_data = result["teams"][0]
            assert isinstance(team_data, TeamWithProjectsOutSheme)
            assert team_data.name == team1.name
            assert team_data.member_count == 2
            assert len(team_data.projects) == 1
            
            # Проверка структуры проекта
            project_data = team_data.projects[0]
            assert isinstance(project_data, ProjectWithTasksOutSheme)
            assert project_data.name == project1.name
            assert len(project_data.tasks) == 2
            
            # Проверка структуры задачи
            task_data = project_data.tasks[0]
            assert isinstance(task_data, TaskWithExecutorsOutSheme)
            assert task_data.name == task1.name
            assert len(task_data.executors) == 2


    @pytest.mark.asyncio
    async def test_get_dashboard_data_projects_only(self, mock_session):
        """
        Тест, когда команды пустые, но проекты есть (глобальный список).
        """
        project1 = create_mock_project()
        task1 = create_mock_task()
        project1.project_tasks = [task1]
        
        scalars_mock  = MagicMock()
        unique_mock = MagicMock()
        scalars_mock.unique = MagicMock(return_value=unique_mock)
        unique_mock.all.return_value = [project1]
        
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=scalars_mock)
        
        mock_session.execute.return_value = mock_result
        


        
        mock_repo_instance = MagicMock(spec=dash_module.TeamRepository)
        mock_repo_instance.get_all = AsyncMock(return_value=[])
        
        with patch.object(dash_module, 'TeamRepository', return_value=mock_repo_instance):
            service = DashboardService(session=mock_session)
            
            user_id = uuid4()
            result = await service.get_dashboard_data(user_id)
            
            assert len(result["teams"]) == 0
            assert len(result["projects"]) == 1
            assert result["projects"][0].name == project1.name

    @pytest.mark.asyncio
    async def test_serialize_team(self, dashboard_service):
        """Тест метода _serialize_team."""
        
        # Создаем мок команды с данными
        project1 = create_mock_project()
        task1 = create_mock_task()
        executor1 = create_mock_executor()
        task1.executors = [executor1]
        project1.project_tasks = [task1]
        user1 = create_mock_user()
        
        team1 = create_mock_team()
        team1.users = [user1]
        team1.team_projects = [project1]
        
        result = dashboard_service._serialize_team(team1)
        
        assert isinstance(result, TeamWithProjectsOutSheme)
        assert result.name == team1.name
        assert result.member_count == 1
        assert len(result.projects) == 1
        
        proj_data = result.projects[0]
        assert proj_data.name == project1.name
        assert len(proj_data.tasks) == 1
        
        task_data = proj_data.tasks[0]
        assert task_data.name == task1.name
        assert len(task_data.executors) == 1


    @pytest.mark.asyncio
    async def test_fetch_all_projects_with_tasks(self, mock_session):
        project1 = create_mock_project()
        task1 = create_mock_task()
        executor1 = create_mock_executor()
        task1.executors = [executor1]
        project1.project_tasks = [task1]

        # Настраиваем цепочку мокирования
        mock_result = AsyncMock()
        
        # .scalars() вызывается как обычный метод, поэтому делаем его синхронным MagicMock
        scalars_mock = MagicMock()
        mock_result.scalars = MagicMock(return_value=scalars_mock)
        
        # unique() тоже обычный метод
        unique_mock = MagicMock()
        scalars_mock.unique = MagicMock(return_value=unique_mock)
        
        # Финальное значение
        unique_mock.all.return_value = [project1]
        
        mock_session.execute.return_value = mock_result

        service = DashboardService(session=mock_session)
        result = await service._fetch_all_projects_with_tasks()

        assert len(result) == 1
        assert isinstance(result[0], ProjectWithTasksOutSheme)
        assert result[0].name == project1.name
        assert len(result[0].tasks) == 1
        assert result[0].tasks[0].name == task1.name