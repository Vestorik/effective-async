from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List
from app.src.base.utils import check_time_range



class BaseModelSheme(BaseModel):
    """
    Базовая Pydantic-схема для всех сущностей с идентификатором и метками времени.

    Реализует повторное использование общих полей: id, created_at, updated_at.
    Адаптирована для работы с SQLAlchemy ORM через `from_attributes=True`.

    Модель не содержит бизнес-логики, только структуру данных для API.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,     # ORM-совместимость (aiosqlite/asyncpg/SQLAlchemy)
        "extra": "forbid",            # Запрет лишних полей во входных данных
        "validate_assignment": True   # Валидация при изменении поля после создания
    }


class TimeEventSheme(BaseModel):
    """
    Базовая схема для событий с временным интервалом.

    Используется как mixin для `MeetingSchema` и `EventSchema`.
    Поля: start_datetime, end_datetime.
    """

    start_datetime: datetime
    end_datetime: datetime

    model_config = {"from_attributes": True}




class UserBaseSheme(BaseModelSheme):
    """
    Базовая схема пользователя для входа/создания/обновления.

    Не содержит пароля. Наследуется в `UserCreateSheme` и `UserUpdateSheme`.
    """

    username: str = Field(min_length=2, max_length=50)
    email: EmailStr
    role: str
    team_id: Optional[UUID] = Field(default=None, description="Внешний ключ на команду (необязательный).")


class UserCreateSheme(UserBaseSheme):
    """
    Схема создания пользователя.

    Используется при POST /users для валидации входных данных.
    Содержит пароль (как строку), который будет хэширован в сервисе.
    """

    password: str = Field(min_length=8, max_length=50, description="Открытый пароль (не сохраняется в базе).")
    
class UserUpdateSheme(BaseModelSheme):
    """
    Схема обновления пользователя.

    Используется для PATCH /users/{id}.
    Все поля опциональны, чтобы обновлять только нужные.
    Пароль не поддерживается в обновлении через эту схему (можно добавить отдельно).
    """

    username: Optional[str] = Field(default=None, min_length=2, max_length=50)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    team_id: Optional[UUID] = Field(default=None, description="Внешний ключ на команду (необязательный).")



class UserSheme(UserBaseSheme):
    """
    Схема пользователя для входа/создания (с исключением пароля из выхода).

    Может использоваться для валидации входных данных и для сериализации (с exclude=True).
    Пароль исключён из `model_dump()` через `Field(exclude=True)`.
    """

    password: str = Field(min_length=8, max_length=50, exclude=True)


class UserOutSheme(BaseModelSheme):
    """
    Схема пользователя для выхода (GET /users/{id}).

    Не содержит пароля. Не содержит team_id (можно добавить при необходимости).
    Готова к отправке клиенту.
    """

    username: str
    email: EmailStr
    role: str
    team_id: Optional[UUID] = Field(default=None, description="Идентификатор команды (если пользователь в команде).")


class TeamSchema(BaseModelSheme):
    """
    Схема команды для выхода (GET).

    Содержит только безопасные поля: id, временные метки и название.
    Не включает вложенные сущности (users, projects), чтобы избежать рекурсии.
    """

    name: str

class TeamCreate(TeamSchema):
    manager_id : UUID

class TeamWithUsersSheme(TeamSchema):
    """
    Схема команды с вложенным списком пользователей.

    Используется при GET /teams/{id}/users для загрузки всех участников.
    Внимание: не включает project-связи, чтобы избежать цикличности.
    """

    users: List["UserOutSheme"]

class TeamUpdateSheme(BaseModel):
    """
    Схема обновления команды.

    Все поля опциональны.
    """

    name: Optional[str] = Field(default=None, min_length=2, max_length=100)


class ProjectSchema(BaseModelSheme):
    """
    Схема проекта для выхода.

    Не содержит вложенных связей (teams, tasks) — для избежания рекурсии.
    """

    name: str
    description: Optional[str] = Field(default=None, description="Описание проекта.")


class ProjectCreate(BaseModel):
    """Входная схема создания проекта."""
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    team_ids: Optional[List[UUID]] = Field(default=None, description="Список ID команд, участвующих в проекте.")


class ProjectUpdate(BaseModel):
    """Входная схема обновления проекта."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    team_ids: Optional[List[UUID]] = Field(default=None, description="Список ID команд, участвующих в проекте.")


class TeamWithProjectsSheme(TeamSchema):
    """
    Схема команды с вложенным списком проектов.

    Используется при GET /teams/{id}/projects.
    """

    team_projects: List["ProjectSchema"]


class TaskExecutorOutSheme(BaseModelSheme):
    """
    Схема исполнителя задачи для выхода.

    Содержит user_id, estimate и мета-данные.
    """

    task_id: UUID
    user_id: UUID
    estimate: Optional[int] = Field(default=None, description="Оценка исполнителя задачи")


class AddExecutor(BaseModel):
    """Входная схема для добавления исполнителя."""
    user_id: UUID
    estimate: Optional[int] = None


class TaskUpdateSheme(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None

class TaskOutSheme(BaseModelSheme):
    """
    Схема задачи для выхода.

    Не содержит executors/parent/sub_tasks для избежания рекурсии.
    Можно добавить в отдельные схемы (TaskWithExecutorsSheme, TaskWithSubTasksSheme).
    """

    name: str
    description: Optional[str] = Field(default=None, description="Описание задачи.")
    project_id: Optional[UUID] = Field(default=None, description="Идентификатор проекта (если задача привязана к проекту).")
    parent_id: Optional[UUID] = Field(default=None, description="Идентификатор родительской задачи (если задача подзадача).")


class TaskWithExecutorsSheme(TaskOutSheme):
    """
    Схема задачи с исполнителями.

    Используется при GET /tasks/{id}/executors.
    """

    executors: List["TaskExecutorOutSheme"]


class TaskCreate(BaseModel):
    """Входная схема создания задачи."""
    name: str
    description: Optional[str] = None
    priority: str = "medium"  # low, medium, high
    parent_id: Optional[UUID] = None
    executor_ids: Optional[List[UUID]] = None


class TaskCreateOutSheme(TaskOutSheme):
    """Схема для выхода при создании задачи."""
    pass

class MeetingSheme(TimeEventSheme):
    """
    Схема встречи.

    Наследует start_datetime и end_datetime от TimeEventSheme.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime


class EventSheme(TimeEventSheme):
    """
    Схема события.

    Наследует start_datetime и end_datetime от TimeEventSheme.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime
    
    

class EventCreate(BaseModel):
    """
    Схема создания события (дедлайн, напоминание).
    """
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=512)
    start_datetime: datetime
    end_datetime: datetime

    @field_validator("end_datetime")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_datetime")
        try:
            check_time_range(start, v)
        except ValueError as e:
            raise ValueError(f"Ошибка валидации времени: {e}")
        return v


class MeetingCreate(BaseModel):
    """
    Схема создания встречи.
    """
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=512)
    start_datetime: datetime
    end_datetime: datetime

    @field_validator("end_datetime")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_datetime")
        try:
            check_time_range(start, v)
        except ValueError as e:
            raise ValueError(f"Ошибка валидации времени: {e}")
        return v
    



    
# 🔁 Ручное исправление циклической зависимости для вложенных схем
# (Pydantic v2 не поддерживает forward-ссылки в моделях-наследниках)
TeamWithUsersSheme.model_rebuild()
TeamWithProjectsSheme.model_rebuild()
TaskWithExecutorsSheme.model_rebuild()

