# tests/unit_tests/schemas/test_schemas.py

"""
Тесты для Pydantic схем (DTOs).

Покрытие:
1. Валидация полей (мин/макс длины, required).
2. Обработка None для опциональных полей.
3. Исключение чувствительных данных (password) из вывода.
4. Валидация временных интервалов (start < end).
5. Структура наследования и конфигурация моделей.

Критерии приемки:
- Все схемы валидируют входные данные корректно.
- Опциональные поля обрабатываются как default=None.
- Поля, помеченные exclude=True, не попадают в вывод.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.src.api.shems import (
    EventCreate,
    MeetingCreate,
    ProjectCreate,
    ProjectOutSchema,
    ProjectUpdate,
    ProjectWithTasksOutSheme,
    TaskCreate,
    TaskExecutorOutSheme,
    TaskUpdateSheme,
    TaskWithExecutorsOutSheme,
    TeamCreate,
    TeamUpdateSheme,
    UserCreateSheme,
    UserOutSheme,
    UserSheme,
    UserUpdateSheme,
)

# Фикстуры для тестовых данных


@pytest.fixture
def valid_datetime_range():
    """
    Возвращает пару валидных дат: start и end (начало < конец).
    
    Возвращает:
        tuple[datetime, datetime]: Кортеж с датой начала и окончания.
    """
    start = datetime(2023, 10, 1, 10, 0, 0)
    end = datetime(2023, 10, 1, 11, 0, 0)
    return start, end


@pytest.fixture
def invalid_datetime_range():
    """
    Возвращает пару невалидных дат: end < start.
    
    Возвращает:
        tuple[datetime, datetime]: Кортеж с датой начала и окончания (конец раньше начала).
    """
    start = datetime(2023, 10, 1, 11, 0, 0)
    end = datetime(2023, 10, 1, 10, 0, 0)
    return start, end


class TestUserSchemas:
    """Тесты для пользовательских схем."""

    def test_user_create_success(self, valid_datetime_range):
        """
        Проверка: UserCreateSheme валидирует корректные данные.
        
        Arrange: Валидные данные для создания пользователя.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно.
        """
        # Arrange
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "securepassword123",
            "role": "user",
            "team_id": None
        }
        
        # Act
        user = UserCreateSheme(**data)
        
        # Assert
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password == "securepassword123"
        assert user.role == "user"
        assert user.team_id is None

    def test_user_create_invalid_email(self):
        """
        Проверка: UserCreateSheme отклоняет невалидный email.
        
        Arrange: Данные с невалидным email.
        Act: Попытка создания экземпляра.
        Assert: Вызывается ValidationError.
        """
        # Arrange
        data = {
            "username": "testuser",
            "email": "invalid-email",
            "password": "securepassword123",
            "role": "user"
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreateSheme(**data)

    def test_user_create_password_too_short(self):
        """
        Проверка: UserCreateSheme отклоняет короткий пароль.
        
        Arrange: Данные с коротким паролем (меньше 8 символов).
        Act: Попытка создания экземпляра.
        Assert: Вызывается ValidationError.
        """
        # Arrange
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "short",
            "role": "user"
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreateSheme(**data)

    def test_user_create_password_too_long(self):
        """
        Проверка: UserCreateSheme отклоняет слишком длинный пароль.
        
        Arrange: Данные с паролем более 50 символов.
        Act: Попытка создания экземпляра.
        Assert: Вызывается ValidationError.
        """
        # Arrange
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "a" * 51,
            "role": "user"
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreateSheme(**data)

    def test_user_update_partial_fields(self):
        """
        Проверка: UserUpdateSheme обновляет только указанные поля.
        
        Arrange: Данные только с одним полем для обновления.
        Act: Создание экземпляра схемы.
        Assert: Другие поля остаются None.
        """
        # Arrange
        data = {
            "username": "updated_user"
        }
        
        # Act
        user = UserUpdateSheme(**data)
        
        # Assert
        assert user.username == "updated_user"
        assert user.email is None
        assert user.role is None
        assert user.team_id is None

    def test_user_out_schema_excludes_password(self):
        """
        Проверка: UserOutSheme не содержит поля password.
        
        Arrange: Данные пользователя.
        Act: Создание экземпляра и конвертация в dict.
        Assert: Поле 'password' отсутствует в словаре.
        """
        # Arrange
        data = {

            "username": "testuser",
            "email": "test@example.com",
            "role": "user",
        }
        
        # Act
        user = UserOutSheme(**data)
        user_dict = user.model_dump()
        
        # Assert
        assert "password" not in user_dict
        assert user_dict["username"] == "testuser"

    def test_user_sheme_excludes_password_from_dump(self):
        """
        Проверка: UserSheme исключает пароль из вывода при dump.
        
        Arrange: Данные с паролем.
        Act: Создание экземпляра и конвертация в dict.
        Assert: Поле 'password' отсутствует в словаре.
        """
        # Arrange
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "role": "user",
            "team_id": uuid4(),
            "password": "secret123"
        }
        
        # Act
        user = UserSheme(**data)
        user_dict = user.model_dump()
        
        # Assert
        assert "password" not in user_dict
        assert "team_id" in user_dict


class TestTeamSchemas:
    """Тесты для схем команд."""

    def test_team_create_success(self):
        """
        Проверка: TeamCreate валидирует корректные данные.
        
        Arrange: Валидные данные для создания команды.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно.
        """
        # Arrange
        data = {
            "name": "Dev Team",
            "manager_id": uuid4(),
        }
        
        # Act
        team = TeamCreate(**data)
        
        # Assert
        assert team.name == "Dev Team"
        assert isinstance(team.manager_id, UUID)

    def test_team_update_partial(self):
        """
        Проверка: TeamUpdateSheme принимает только часть полей.
        
        Arrange: Данные только с полем name.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно, остальные поля None.
        """
        # Arrange
        data = {
            "name": "Updated Team Name"
        }
        
        # Act
        team = TeamUpdateSheme(**data)
        
        # Assert
        assert team.name == "Updated Team Name"


class TestProjectSchemas:
    """Тесты для схем проектов."""

    def test_project_create_success(self):
        """
        Проверка: ProjectCreate валидирует корректные данные.
        
        Arrange: Валидные данные для создания проекта.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно.
        """
        # Arrange
        data = {
            "name": "My Project",
            "description": "Test project description",
            "team_ids": [uuid4(), uuid4()]
        }
        
        # Act
        project = ProjectCreate(**data)
        
        # Assert
        assert project.name == "My Project"
        assert project.description == "Test project description"
        assert len(project.team_ids) == 2  # ty: ignore[invalid-argument-type]

    def test_project_create_missing_name(self):
        """
        Проверка: ProjectCreate отклоняет данные без названия.
        
        Arrange: Данные без обязательного поля name.
        Act: Попытка создания экземпляра.
        Assert: Вызывается ValidationError.
        """
        # Arrange
        data = {
            "description": "No name project"
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            ProjectCreate(**data)

    def test_project_update_optional_fields(self):
        """
        Проверка: ProjectUpdate принимает любые комбинации опциональных полей.
        
        Arrange: Данные только с описанием.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно.
        """
        # Arrange
        data = {
            "description": "Updated description"
        }
        
        # Act
        project = ProjectUpdate(**data)
        
        # Assert
        assert project.description == "Updated description"
        assert project.name is None


class TestTaskSchemas:
    """Тесты для схем задач."""

    def test_task_create_success(self):
        """
        Проверка: TaskCreate валидирует корректные данные.
        
        Arrange: Валидные данные для создания задачи.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно, приоритет по умолчанию medium.
        """
        # Arrange
        data = {
            "name": "New Task",
            "description": "Task description",
            "priority": "high",
            "parent_id": None,
            "executor_ids": [uuid4()]
        }
        
        # Act
        task = TaskCreate(**data)
        
        # Assert
        assert task.name == "New Task"
        assert task.priority == "high"
        assert len(task.executor_ids) == 1  # ty: ignore[invalid-argument-type]

    def test_task_create_default_priority(self):
        """
        Проверка: TaskCreate устанавливает приоритет 'medium' по умолчанию.
        
        Arrange: Данные без указания приоритета.
        Act: Создание экземпляра схемы.
        Assert: Приоритет равен 'medium'.
        """
        # Arrange
        data = {
            "name": "Task without priority"
        }
        
        # Act
        task = TaskCreate(**data)
        
        # Assert
        assert task.priority == "medium"

    def test_task_update_partial(self):
        """
        Проверка: TaskUpdateSheme обновляет только указанные поля.
        
        Arrange: Данные только с описанием.
        Act: Создание экземпляра схемы.
        Assert: Другие поля остаются None.
        """
        # Arrange
        data = {
            "description": "Updated description"
        }
        
        # Act
        task = TaskUpdateSheme(**data)
        
        # Assert
        assert task.description == "Updated description"
        assert task.name is None
        assert task.priority is None


class TestEventSchemas:
    """Тесты для схем событий и встреч."""

    def test_event_create_success(self, valid_datetime_range):
        """
        Проверка: EventCreate валидирует корректные данные с валидным временем.
        
        Arrange: Валидные данные с временем start < end.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно.
        """
        # Arrange
        start, end = valid_datetime_range
        data = {
            "name": "Test Event",
            "description": "Test description",
            "start_datetime": start,
            "end_datetime": end
        }
        
        # Act
        event = EventCreate(**data)
        
        # Assert
        assert event.name == "Test Event"
        assert event.start_datetime == start
        assert event.end_datetime == end

    def test_event_create_invalid_time_range(self, invalid_datetime_range):
        """
        Проверка: EventCreate отклоняет данные, где end < start.
        
        Arrange: Данные с временем, где конец раньше начала.
        Act: Попытка создания экземпляра.
        Assert: Вызывается ValidationError.
        """
        # Arrange
        start, end = invalid_datetime_range
        data = {
            "name": "Invalid Event",
            "start_datetime": start,
            "end_datetime": end
        }
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            EventCreate(**data)
            
        # Проверяем, что ошибка связана с валидацией времени
        assert len(exc_info.value.errors()) > 0

    def test_meeting_create_success(self, valid_datetime_range):
        """
        Проверка: MeetingCreate валидирует корректные данные с валидным временем.
        
        Arrange: Валидные данные с временем start < end.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно.
        """
        # Arrange
        start, end = valid_datetime_range
        data = {
            "name": "Test Meeting",
            "description": "Meeting description",
            "start_datetime": start,
            "end_datetime": end
        }
        
        # Act
        meeting = MeetingCreate(**data)
        
        # Assert
        assert meeting.name == "Test Meeting"
        assert meeting.start_datetime == start
        assert meeting.end_datetime == end

    def test_meeting_create_invalid_time_range(self, invalid_datetime_range):
        """
        Проверка: MeetingCreate отклоняет данные, где end < start.
        
        Arrange: Данные с временем, где конец раньше начала.
        Act: Попытка создания экземпляра.
        Assert: Вызывается ValidationError.
        """
        # Arrange
        start, end = invalid_datetime_range
        data = {
            "name": "Invalid Meeting",
            "start_datetime": start,
            "end_datetime": end
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            MeetingCreate(**data)
            
            


class TestNestedOutSchemas:
    """Тесты для вложенных схем вывода (Out schemas with lists)."""

    def test_task_executor_out_schema_success(self):
        """
        Проверка: TaskExecutorOutSheme валидирует корректные данные.
        
        Arrange: Валидные данные для вывода исполнителя.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно.
        """
        # Arrange
        data = {
  
            "task_id": uuid4(),
            "user_id": uuid4(),
            "estimate": 10,
            "username": "John Doe",

        }
        
        # Act
        executor = TaskExecutorOutSheme(**data)
        
        # Assert
        assert executor.task_id == data["task_id"]
        assert executor.username == "John Doe"
        assert executor.estimate == 10

    def test_task_with_executors_out_schema_success(self):
        """
        Проверка: TaskWithExecutorsOutSheme валидирует задачу с исполнителями.
        
        Arrange: Валидные данные для вывода задачи с исполнителями.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно, список исполнителей валиден.
        """
        # Arrange
        executor_data_1 = {
            "task_id": uuid4(),
            "user_id": uuid4(),
            "estimate": 10,
            "username": "Alice",

        }
        executor_data_2 = {

            "task_id": executor_data_1["task_id"],
            "user_id": uuid4(),
            "estimate": 5,
            "username": "Bob",

        }
        
        data = {
            "name": "Complex Task",
            "description": "Task with executors",
            "project_id": None,
            "parent_id": None,
            "executors": [executor_data_1, executor_data_2]
        }
        
        # Act
        task = TaskWithExecutorsOutSheme(**data)  # ty: ignore[invalid-argument-type]
        
        # Assert
        assert task.name == "Complex Task"
        assert len(task.executors) == 2
        assert task.executors[0].username == "Alice"
        assert task.executors[1].username == "Bob"

    def test_project_out_schema_success(self):
        """
        Проверка: ProjectOutSchema валидирует корректные данные.
        
        Arrange: Валидные данные для вывода проекта.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно.
        """
        # Arrange
        data = {

            "name": "My Project",
            "description": "Test project description",
            "team_ids": [uuid4(), uuid4()],
        }
        
        # Act
        project = ProjectOutSchema(**data)
        
        # Assert
        assert project.name == "My Project"
        assert len(project.team_ids) == 2  # ty: ignore[invalid-argument-type]

    def test_project_with_tasks_out_schema_success(self):
        """
        Проверка: ProjectWithTasksOutSheme валидирует проект с задачами.
        
        Arrange: Валидные данные для вывода проекта с задачами.
        Act: Создание экземпляра схемы.
        Assert: Экземпляр создан успешно, список задач валиден.
        """
        # Arrange
        task_data = {

            "name": "Task 1",
            "description": "Task description",
            "project_id": None,
            "parent_id": None,
            "executors": []
        }
        
        data = {
            "name": "Project with Tasks",
            "description": "Main project",
            "team_ids": None,

            "tasks": [task_data]
        }
        
        # Act
        project = ProjectWithTasksOutSheme(**data)
        
        # Assert
        assert project.name == "Project with Tasks"
        assert len(project.tasks) == 1
        assert project.tasks[0].name == "Task 1"
        assert isinstance(project.tasks[0].executors, list)