"""Тесты репозиториев database/repositories.py."""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.src.dal.database.models import UserModel, TeamModel, ProjectModel, TaskModel, TaskExecutorModel, MeetingModel, EventModel
from app.src.dal.database.repositories import (
    UserRepository,
    TeamRepository,
    ProjectRepository,
    TaskRepository,
    TaskExecutorRepository,
    MeetingRepository,
    EventRepository,
)


class TestUserRepository:
    """Тесты UserRepository."""

    @pytest.fixture
    async def user_repo(self, session_maker, test_engine):
        """Создаёт UserRepository с тестовой сессией."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return UserRepository(session)

    async def test_create_user(self, user_repo, test_session):
        """Тест создания пользователя."""
        user = UserModel(
            username="testuser",
            email="test@example.com",
            role="user",
        )
        user.set_password("password123")
        
        created_user = await user_repo.create(user)
        await test_session.commit()
        
        assert created_user.id is not None
        assert created_user.username == "testuser"
        assert created_user.email == "test@example.com"

    async def test_get_by_id(self, user_repo, test_session):
        """Тест получения пользователя по ID."""
        user = UserModel(
            username="testuser",
            email="test@example.com",
            role="user",
        )
        user.set_password("password123")
        test_session.add(user)
        await test_session.commit()
        await test_session.flush()
        
        retrieved_user = await user_repo.get_by_id(user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == user.id

    async def test_get_by_email(self, user_repo, test_session):
        """Тест получения пользователя по email."""
        user = UserModel(
            username="testuser",
            email="test@example.com",
            role="user",
        )
        user.set_password("password123")
        test_session.add(user)
        await test_session.commit()
        
        retrieved_user = await user_repo.get_by_email("test@example.com")
        
        assert retrieved_user is not None
        assert retrieved_user.email == "test@example.com"

    async def test_get_by_email_not_found(self, user_repo):
        """Тест получения несуществующего пользователя по email."""
        result = await user_repo.get_by_email("nonexistent@example.com")
        
        assert result is None

    async def test_get_by_role(self, user_repo, test_session):
        """Тест получения пользователей по роли."""
        user1 = UserModel(username="admin1", email="admin1@example.com", role="admin")
        user1.set_password("password123")
        user2 = UserModel(username="admin2", email="admin2@example.com", role="admin")
        user2.set_password("password123")
        test_session.add_all([user1, user2])
        await test_session.commit()
        
        admins = await user_repo.get_by_role("admin")
        
        assert len(admins) == 2

    async def test_update_user(self, user_repo, test_session):
        """Тест обновления пользователя."""
        user = UserModel(username="oldname", email="test@example.com", role="user")
        user.set_password("password123")
        test_session.add(user)
        await test_session.commit()
        
        user.username = "newname"
        updated_user = await user_repo.update(user)
        await test_session.commit()
        
        assert updated_user.username == "newname"

    async def test_delete_user(self, user_repo, test_session):
        """Тест удаления пользователя."""
        user = UserModel(username="testuser", email="test@example.com", role="user")
        user.set_password("password123")
        test_session.add(user)
        await test_session.commit()
        
        await user_repo.delete(user)
        await test_session.commit()
        
        result = await test_session.execute(
            test_session.query(UserModel).filter(UserModel.id == user.id)
        )
        assert result.scalar_one_or_none() is None

    async def test_get_all(self, user_repo, test_session):
        """Тест получения всех пользователей."""
        user1 = UserModel(username="user1", email="user1@example.com", role="user")
        user1.set_password("password123")
        user2 = UserModel(username="user2", email="user2@example.com", role="user")
        user2.set_password("password123")
        test_session.add_all([user1, user2])
        await test_session.commit()
        
        users = await user_repo.get_all()
        
        assert len(users) == 2

    async def test_get_all_paginated(self, user_repo, test_session):
        """Тест пагинации пользователей."""
        for i in range(5):
            user = UserModel(username=f"user{i}", email=f"user{i}@example.com", role="user")
            user.set_password("password123")
            test_session.add(user)
        await test_session.commit()
        
        users, total = await user_repo.get_all_paginated(page=1, page_size=3)
        
        assert len(users) == 3
        assert total == 5

    async def test_get_all_paginated_with_role_filter(self, user_repo, test_session):
        """Тест пагинации с фильтрацией по роли."""
        admin = UserModel(username="admin", email="admin@example.com", role="admin")
        admin.set_password("password123")
        user = UserModel(username="user", email="user@example.com", role="user")
        user.set_password("password123")
        test_session.add_all([admin, user])
        await test_session.commit()
        
        admins, total = await user_repo.get_all_paginated(page=1, page_size=10, role="admin")
        
        assert len(admins) == 1
        assert total == 1
        assert admins[0].role == "admin"


class TestTeamRepository:
    """Тесты TeamRepository."""

    @pytest.fixture
    async def team_repo(self, session_maker, test_engine):
        """Создаёт TeamRepository."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return TeamRepository(session)

    async def test_create_team(self, team_repo, test_session):
        """Тест создания команды."""
        team = TeamModel(name="Dev Team")
        
        created_team = await team_repo.create(team)
        await test_session.commit()
        
        assert created_team.id is not None
        assert created_team.name == "Dev Team"

    async def test_get_by_id(self, team_repo, test_session):
        """Тест получения команды по ID."""
        team = TeamModel(name="Dev Team")
        test_session.add(team)
        await test_session.commit()
        
        retrieved_team = await team_repo.get_by_id(team.id)
        
        assert retrieved_team is not None
        assert retrieved_team.id == team.id

    async def test_get_by_name(self, team_repo, test_session):
        """Тест получения команды по названию."""
        team = TeamModel(name="Dev Team")
        test_session.add(team)
        await test_session.commit()
        
        retrieved_team = await team_repo.get_by_name("Dev Team")
        
        assert retrieved_team is not None
        assert retrieved_team.name == "Dev Team"

    async def test_get_by_name_not_found(self, team_repo):
        """Тест получения несуществующей команды."""
        result = await team_repo.get_by_name("Nonexistent")
        
        assert result is None


class TestProjectRepository:
    """Тесты ProjectRepository."""

    @pytest.fixture
    async def project_repo(self, session_maker, test_engine):
        """Создаёт ProjectRepository."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return ProjectRepository(session)

    async def test_create_project(self, project_repo, test_session):
        """Тест создания проекта."""
        project = ProjectModel(name="Test Project", description="Project description")
        
        created_project = await project_repo.create(project)
        await test_session.commit()
        
        assert created_project.id is not None
        assert created_project.name == "Test Project"

    async def test_get_by_id(self, project_repo, test_session):
        """Тест получения проекта по ID."""
        project = ProjectModel(name="Test Project")
        test_session.add(project)
        await test_session.commit()
        
        retrieved_project = await project_repo.get_by_id(project.id)
        
        assert retrieved_project is not None

    async def test_get_by_name(self, project_repo, test_session):
        """Тест получения проекта по названию."""
        project = ProjectModel(name="Test Project")
        test_session.add(project)
        await test_session.commit()
        
        retrieved_project = await project_repo.get_by_name("Test Project")
        
        assert retrieved_project is not None


class TestTaskRepository:
    """Тесты TaskRepository."""

    @pytest.fixture
    async def task_repo(self, session_maker, test_engine):
        """Создаёт TaskRepository."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return TaskRepository(session)

    async def test_create_task(self, task_repo, test_session):
        """Тест создания задачи."""
        task = TaskModel(name="Test Task", description="Task description")
        
        created_task = await task_repo.create(task)
        await test_session.commit()
        
        assert created_task.id is not None

    async def test_get_by_id(self, task_repo, test_session):
        """Тест получения задачи по ID."""
        task = TaskModel(name="Test Task")
        test_session.add(task)
        await test_session.commit()
        
        retrieved_task = await task_repo.get_by_id(task.id)
        
        assert retrieved_task is not None


class TestTaskExecutorRepository:
    """Тесты TaskExecutorRepository."""

    @pytest.fixture
    async def executor_repo(self, session_maker, test_engine):
        """Создаёт TaskExecutorRepository."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return TaskExecutorRepository(session)

    async def test_create_executor(self, executor_repo, test_session):
        """Тест создания исполнителя задачи."""
        user = UserModel(username="user", email="user@example.com", role="user")
        user.set_password("password123")
        task = TaskModel(name="Test Task")
        
        test_session.add_all([user, task])
        await test_session.commit()
        
        executor = TaskExecutorModel(user=user, task=task, estimate=8)
        created_executor = await executor_repo.create(executor)
        await test_session.commit()
        
        assert created_executor.id is not None


class TestMeetingAndEventRepository:
    """Тесты MeetingRepository и EventRepository."""

    @pytest.fixture
    async def meeting_repo(self, session_maker, test_engine):
        """Создаёт MeetingRepository."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return MeetingRepository(session)

    @pytest.fixture
    async def event_repo(self, session_maker, test_engine):
        """Создаёт EventRepository."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return EventRepository(session)

    async def test_meeting_create_and_get(self, meeting_repo, test_session):
        """Тест создания и получения встречи."""
        meeting = MeetingModel(
            start_datetime="2024-01-01 10:00:00+00",
            end_datetime="2024-01-01 11:00:00+00"
        )
        test_session.add(meeting)
        await test_session.commit()
        
        retrieved_meeting = await meeting_repo.get_by_id(meeting.id)
        
        assert retrieved_meeting is not None

    async def test_event_create_and_get(self, event_repo, test_session):
        """Тест создания и получения события."""
        event = EventModel(
            start_datetime="2024-01-01 10:00:00+00",
            end_datetime="2024-01-01 11:00:00+00"
        )
        test_session.add(event)
        await test_session.commit()
        
        retrieved_event = await event_repo.get_by_id(event.id)
        
        assert retrieved_event is not None
