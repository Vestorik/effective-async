from operator import index
from datetime import datetime, timezone
from enum import Enum
from logging import getLogger
from uuid import uuid4, UUID
from passlib.context import CryptContext
from sqlalchemy import (
    DateTime,
    String, PrimaryKeyConstraint,
)
from typing import Optional
from sqlalchemy import Table, Column, ForeignKey, Integer
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID


from sqlalchemy.orm import DeclarativeBase

logger = getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BaseModel(DeclarativeBase):
    """
    Абстрактная базовая модель для всех ORM-сущностей.

    Содержит общие поля:
        id (UUID) — уникальный идентификатор.
        created_at (datetime) — дата и время создания записи в UTC.

    Не содержит бизнес-логики. Все модели наследуют эти поля по умолчанию.
    """

    __abstract__ = True

    id: Mapped[SQL_UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Уникальный идентификатор записи (UUID).",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Дата и время создания записи в UTC.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Время последнего обновления",
    )


class TimeEvent(DeclarativeBase):
    __abstract__ = True

    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Дата и время начала события"
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Время окончания события"
    )


class RoleModel(Enum):
    ADMIN = "admin"
    USER = "user"


class UserModel(BaseModel):
    """
    Модель пользователя системы.

    Представляет таблицу 'users' в базе данных и содержит основные поля: email, роль и дату создания.
    Класс наследует общие ORM-методы от Base: save, delete, get, all, update_by_id.

    Атрибуты:
        email (str): Уникальная электронная почта пользователя.
        role (str): Роль пользователя в системе (например, 'admin', 'user').
        created_at (datetime): Дата и время создания записи в UTC.

    Методы:
        get_by_email: Асинхронно возвращает пользователя по email.
        get_users_by_role: Асинхронно возвращает всех пользователей с указанной ролью.

    Примечания:
        - Поле email должно быть уникальным и обязательным.
        - Роль пользователя является обязательным полем.
        - Дата создания автоматически устанавливается при создании записи.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(255),
        unique=False,
        nullable=False,
        comment="Имя пользователя. Обязательной поле.",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Электронная почта пользователя. Должна быть уникальной и обязательной.",
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default="user",
        nullable=False,
        comment="Роль пользователя в системе (например, 'admin', 'user'). Обязательное поле.",
    )

    hashed_password: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Хэшированный пароль пользователя, созданный с помощью bcrypt.",
    )

    def check_password(self, plain_password: str) -> bool:
        """
        Проверяет, соответствует ли открытый пароль хэшированному.

        Аргументы:
            plain_password (str): Пароль, введённый пользователем (в открытом виде).

        Возвращает:
            bool: True, если пароль верный; иначе False.
        """
        return pwd_context.verify(plain_password, self.hashed_password)

    def set_password(self, password: str) -> None:
        """
        Устанавливает и хэширует пароль пользователя.

        Аргументы:
            password (str): Пароль в открытом виде.
        """
        self.hashed_password = pwd_context.hash(password)

    # 1:n один пользователь одна комманда, в комманде много пользователей
    team_id: Mapped[Optional[UUID]] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("teams.id"),
        nullable=True,
        comment="Внешний ключ на команду (1:N, пользователь в одной команде).",
    )
    team: Mapped[Optional[TeamModel]] = relationship(
        back_populates="users",
        lazy="joined",
        uselist=False,  # <-- 1:1 для пользователя
    )
    task_executors: Mapped[list[TaskExecutorModel]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


team_project_table = Table(
    "team_projects",
    BaseModel.metadata,
    Column("team_id", SQL_UUID(as_uuid=True), ForeignKey("teams.id"), primary_key=True),
    Column("project_id", SQL_UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True),
)


class TeamModel(BaseModel):
    __tablename__ = "teams"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # 1:n один пользователь одна комманда, в комманде много пользователей
    users: Mapped[list[UserModel]] = relationship(
        back_populates="team",
        lazy="joined",
    )

    # n:m у команды много проектов, в 1 проекте может быть несколько команд
    team_projects: Mapped[list[ProjectModel]] = relationship(
        secondary=team_project_table,
        back_populates="project_teams",
        lazy="joined",
    )


class ProjectModel(BaseModel):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Название проекта.", unique=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="Описание проекта."
    )

    # n:m у команды много проектов, в 1 проекте может быть несколько команд
    project_teams: Mapped[list[TeamModel]] = (
        relationship( 
            secondary=team_project_table,
            back_populates="team_projects",
        )
    )

    # 1:n У проекта много задач, у задач один проект
    project_tasks: Mapped[list[TaskModel]] = relationship(
        back_populates="project", 
        cascade="all, delete-orphan",
    )


class TaskModel(BaseModel):
    __tablename__ = "tasks"

    name: Mapped[str] = mapped_column(String(124), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=True)

    #  sub tasks
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=True,
        index=True,
    )
    parent: Mapped[TaskModel | None] = relationship(
        "TaskModel",
        remote_side=[parent_id],
        back_populates="sub_tasks",
    )
    sub_tasks: Mapped[list[TaskModel]] = relationship(
        "TaskModel",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    #  relationships
    executors: Mapped[list[TaskExecutorModel]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="joined",
    )

    project_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
        comment="Внешний ключ на проект (1:N).",
    )
    project: Mapped[Optional[ProjectModel]] = relationship(
        back_populates="project_tasks",
    )


class TaskExecutorModel(BaseModel):
    __tablename__ = "task_executors"
    __table_args__ = (
    PrimaryKeyConstraint('user_id', 'task_id'),
)

    #  Main field
    estimate: Mapped[int] = mapped_column(
        Integer, nullable=True, comment="Оценка исполнителя за выполненую задачу"
    )

    user_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey('users.id'),
        nullable=False,
        comment="Внешний ключ на пользователя (обязательный, исполнитель).",
    )
    user: Mapped["UserModel"] = relationship(
        back_populates="task_executors",
        lazy="joined",
    )

    task_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey('tasks.id'),
        nullable=False,
        comment="Внешний ключ на задачу (обязательный, задача исполнителя).",
    )
    task: Mapped["TaskModel"] = relationship(
        back_populates="executors",
        lazy="joined",
    )



class MeetingModel(BaseModel, TimeEvent):
    __tablename__ = "meetings"


class EventModel(BaseModel, TimeEvent):
    __tablename__ = "events"