"""Тесты ORM-моделей database/models.py."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.src.dal.database.models import (
    BaseModel,
    TimeEventMixin,
    UserModel,
    TeamModel,
    ProjectModel,
    TaskModel,
    TaskExecutorModel,
    MeetingModel,
    EventModel,
    pwd_context,
)



assert BaseModel.__abstract__ is True

def test_base_model_fields(self):
    """Тест полей BaseModel."""
    user = UserModel(
        username="testuser",
        email="test@example.com",
        role="user",
    )
    user.set_password("password123")
    
    assert user.id is not None
    assert user.created_at is not None
    assert user.updated_at is not None


class TestTimeEventMixin:
    """Тесты TimeEventMixin."""

    def test_time_event_fields(self):
        """Тест полей TimeEventMixin."""
        event = EventModel(
            start_datetime="2024-01-01 10:00:00+00",
            end_datetime="2024-01-01 11:00:00+00"
        )
        
        assert event.start_datetime is not None
        assert event.end_datetime is not None


class TestUserModel:
    """Тесты UserModel."""

    def test_user_model_fields(self):
        """Тест полей UserModel."""
        user = UserModel(
            username="testuser",
            email="test@example.com",
            role="user",
        )
        user.set_password("password123")
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.hashed_password != "password123"  # Пароль хэширован

    def test_set_password(self):
        """Тест хэширования пароля."""
        user = UserModel(username="testuser", email="test@example.com", role="user")
        user.set_password("password123")
        
        assert user.hashed_password is not None
        assert user.hashed_password != "password123"

    def test_check_password_success(self):
        """Тест успешной проверки пароля."""
        user = UserModel(username="testuser", email="test@example.com", role="user")
        user.set_password("password123")
        
        assert user.check_password("password123") is True

    def test_check_password_failure(self):
        """Тест неуспешной проверки пароля."""
        user = UserModel(username="testuser", email="test@example.com", role="user")
        user.set_password("password123")
        
        assert user.check_password("wrongpassword") is False

    def test_user_model_with_team(self):
        """Тест связи UserModel с TeamModel."""
        team = TeamModel(name="Dev Team")
        user = UserModel(
            username="testuser",
            email="test@example.com",
            role="user",
            team_id=team.id,
        )
        user.set_password("password123")
        
        assert user.team_id == team.id


class TestTeamModel:
    """Тесты TeamModel."""

    def test_team_model_fields(self):
        """Тест полей TeamModel."""
        team = TeamModel(name="Dev Team")
        
        assert team.name == "Dev Team"


class TestProjectModel:
    """Тесты ProjectModel."""

    def test_project_model_fields(self):
        """Тест полей ProjectModel."""
        project = ProjectModel(name="Test Project", description="Project description")
        
        assert project.name == "Test Project"
        assert project.description == "Project description"


class TestTaskModel:
    """Тесты TaskModel."""

    def test_task_model_fields(self):
        """Тест полей TaskModel."""
        task = TaskModel(name="Test Task", description="Task description")
        
        assert task.name == "Test Task"
        assert task.description == "Task description"

    def test_task_model_with_parent(self):
        """Тест родительской и подзадач."""
        parent_task = TaskModel(name="Parent Task")
        sub_task = TaskModel(name="Sub Task", parent_id=parent_task.id)
        
        assert sub_task.parent_id == parent_task.id


class TestTaskExecutorModel:
    """Тесты TaskExecutorModel."""

    def test_task_executor_model_fields(self):
        """Тест полей TaskExecutorModel."""
        user = UserModel(username="testuser", email="test@example.com", role="user")
        user.set_password("password123")
        task = TaskModel(name="Test Task")
        
        executor = TaskExecutorModel(
            user=user,
            task=task,
            estimate=8
        )
        
        assert executor.user_id == user.id
        assert executor.task_id == task.id
        assert executor.estimate == 8


class TestMeetingAndEventModel:
    """Тесты MeetingModel и EventModel."""

    def test_meeting_model_inherits_time_event(self):
        """Тест, что MeetingModel наследует TimeEventMixin."""
        meeting = MeetingModel(
            start_datetime="2024-01-01 10:00:00+00",
            end_datetime="2024-01-01 11:00:00+00"
        )
        
        assert meeting.start_datetime is not None
        assert meeting.end_datetime is not None

    def test_event_model_inherits_time_event(self):
        """Тест, что EventModel наследует TimeEventMixin."""
        event = EventModel(
            start_datetime="2024-01-01 10:00:00+00",
            end_datetime="2024-01-01 11:00:00+00"
        )
        
        assert event.start_datetime is not None
        assert event.end_datetime is not None


class TestPasswordHashing:
    """Тесты хэширования паролей."""

    def test_password_hashing_with_bcrypt(self):
        """Тест хэширования пароля с bcrypt."""
        user = UserModel(username="testuser", email="test@example.com", role="user")
        user.set_password("password123")
        
        # Проверяем, что хэш начинается с $2b$ (bcrypt)
        assert user.hashed_password.startswith("$2b$") or user.hashed_password.startswith("$2a$")
        
        # Проверяем, что хэш достаточно длинный (bcrypt хэши обычно 60 символов)
        assert len(user.hashed_password) == 60

    def test_different_passwords_different_hashes(self):
        """Тест, что разные пароли дают разные хэши."""
        user1 = UserModel(username="user1", email="user1@example.com", role="user")
        user1.set_password("password1")
        
        user2 = UserModel(username="user2", email="user2@example.com", role="user")
        user2.set_password("password2")
        
        assert user1.hashed_password != user2.hashed_password

    def test_same_password_different_hashes(self):
        """Тест, что один пароль даёт разные хэши при повторном вызове."""
        user = UserModel(username="testuser", email="test@example.com", role="user")
        user.set_password("password123")
        hash1 = user.hashed_password
        
        user.set_password("password123")
        hash2 = user.hashed_password
        
        # Хэши должны быть разными из-за соли
        assert hash1 != hash2
        # Но оба должны проверяться успешно
        assert user.check_password("password123") is True
