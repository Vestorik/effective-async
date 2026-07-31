"""
Модуль ORM-моделей для бизнес-управления (BMA).

Назначение:
    Предоставляет SQLAlchemy-модели для хранения сущностей системы:
    - Пользователи (UserModel), команды (TeamModel), проекты (ProjectModel),
      задачи (TaskModel), исполнители задач (TaskExecutorModel),
      встречи (MeetingModel), события (EventModel).
    - Реализует общие поля (id, created_at, updated_at) через абстрактную базовую модель.
    - Использует UUID как тип primary key, включает поддержку UTC-дат.

Архитектура:
    - BaseModel: абстрактный базовый класс для всех моделей.
    - TimeEventMixin: класс-миксин для моделей с временными рамками (start_datetime, end_datetime).
    - Модели связанные: TeamModel ↔ UserModel (1:N), ProjectModel ↔ TeamModel (M:N),
      ProjectModel ↔ TaskModel (1:N), TaskModel ↔ TaskExecutorModel (1:N),
      TaskModel ↔ UserModel (через TaskExecutorModel, M:N).

Ключевые принципы:
    - DRY: общие поля вынесены в BaseModel.
    - KISS: простые, понятные модели без лишней абстракции.
    - Composition over Inheritance: связи реализованы через relationship(), а не множественное наследование.
    - Twelve-Factor App: настройки БД вынесены в переменные окружения (не в код).
    - SOLID: соблюдение принципов Single Responsibility и Dependency Inversion.

Типы данных:
    - id: UUID (SQL_UUID(as_uuid=True)), генерируется client-side через uuid4.
    - datetime: DateTime(timezone=True) — сохраняется в UTC с учетом временных зон.
    - Временные ограничения: start_datetime и end_datetime проверяются на уровне БД через PostgreSQL-триггеры.

Поля моделей:
    - BaseModel: id (UUID), created_at (datetime), updated_at (datetime).
    - TimeEvent: start_datetime (datetime), end_datetime (datetime).
    - UserModel: username (str), email (str, unique), role (str, enum), hashed_password (str).
    - TeamModel: name (str).
    - ProjectModel: name (str, unique), description (str | None).
    - TaskModel: name (str), description (str | None), parent_id (UUID | None, self-reference).
    - TaskExecutorModel: user_id, task_id (composite primary key), estimate (int | None).
    - MeetingModel, EventModel: наследуют TimeEvent.

Связи:
    - 1:1: UserModel.team — один пользователь в одной команде.
    - 1:N: TeamModel.users, ProjectModel.project_tasks, TaskModel.executors.
    - M:N: TeamModel ↔ ProjectModel (через team_project_table).
    - Самоссылка: TaskModel.parent/sub_tasks — вложенность задач.

Валидация и безопасность:
    - Уникальность email в UserModel.
    - Хэширование паролей через bcrypt (passlib).
    - Проверка временных интервалов (start_datetime < end_datetime) через PostgreSQL-триггеры для EventModel, MeetingModel.
    - Каскадное удаление: sub_tasks, project_tasks, task_executors удаляются при удалении родителя.

Ограничения:
    - PostgreSQL-специфичные типы (SQL_UUID, DateTime(timezone=True)) требуют PostgreSQL ≥ 9.6.
    - Триггеры для TimeEvent-моделей не проверяют временные зоны — сравнение происходит в UTC.
    - Имена моделей и полей — в стиле snake_case (PEP 8).

Применение:
    - Основной слой ORM для работы с БД через репозитории.
    - Используется в слое DAL (Data Access Layer) и сервисах.
    - Все модели поддерживают CRUD-операции через ORM-сессию.

Примеры:
    # Создание пользователя
    user = UserModel(username="alex", email="alex@example.com", role="user")
    user.set_password("secure_password")
    session.add(user)
    await session.commit()

    # Создание команды с пользователями
    team = TeamModel(name="Dev Team")
    user.team = team
    session.add(team)
    await session.commit()

    # Создание задачи с исполнителем
    task = TaskModel(name="Fix bug", description="Critical issue in auth")
    executor = TaskExecutorModel(user=user, task=task, estimate=8)
    session.add(task)
    await session.commit()
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from logging import getLogger
from typing import Optional
from uuid import UUID, uuid4

from passlib.context import CryptContext
from sqlalchemy import (
    DDL,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    event,
)
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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


team_project_table = Table(
    "team_projects",
    BaseModel.metadata,
    Column("team_id", SQL_UUID(as_uuid=True), ForeignKey("teams.id"), primary_key=True),
    Column(
        "project_id",
        SQL_UUID(as_uuid=True),
        ForeignKey("projects.id"),
        primary_key=True,
    ),
)


meeting_teams_table = Table(
    "meeting_teams",
    BaseModel.metadata,
    Column(
        "meeting_id",
        SQL_UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "team_id",
        SQL_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


meeting_participants_table = Table(
    "meeting_participants",
    BaseModel.metadata,
    Column(
        "meeting_id",
        SQL_UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        SQL_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class TimeEventMixin:
    __abstract__ = True

    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Дата и время начала события"
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Время окончания события"
    )


class RoleModel(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
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

    refresh_token_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Хэш refresh_token для обеспечения безопасного logout и ротации сессий.",
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
    team: Mapped[Optional["TeamModel"]] = relationship(
        back_populates="users",
        lazy="joined",
        uselist=False,  # <-- 1:1 для пользователя
    )
    task_executors: Mapped[list["TaskExecutorModel"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    comments: Mapped[list["CommentModel"]] = relationship(
        "CommentModel",
        back_populates="author",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    meetings: Mapped[list["MeetingModel"]] = relationship(
        secondary=meeting_teams_table,
        back_populates="participants",
    )


class TeamModel(BaseModel):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # 1:n один пользователь одна комманда, в комманде много пользователей
    users: Mapped[list["UserModel"]] = relationship(
        back_populates="team",
        lazy="joined",
    )

    # n:m у команды много проектов, в 1 проекте может быть несколько команд
    team_projects: Mapped[list["ProjectModel"]] = relationship(
        secondary=team_project_table,
        back_populates="project_teams",
        lazy="joined",
    )

    meetings: Mapped[list["MeetingModel"]] = relationship(
        secondary=meeting_teams_table,
        back_populates="teams",
    )


class ProjectModel(BaseModel):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Название проекта.",
        unique=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="Описание проекта."
    )

    # n:m у команды много проектов, в 1 проекте может быть несколько команд
    project_teams: Mapped[list["TeamModel"]] = relationship(
        secondary=team_project_table,
        back_populates="team_projects",
    )

    # 1:n У проекта много задач, у задач один проект
    project_tasks: Mapped[list["TaskModel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class TaskModel(BaseModel):
    __tablename__ = "tasks"

    name: Mapped[str] = mapped_column(String(124), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=True)

    estimate: Mapped[int] = mapped_column(
        Integer, nullable=True, comment="Оценка задачи"
    )

    id: Mapped[SQL_UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Уникальный идентификатор записи (UUID).",
    )

    #  sub tasks
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=True,
        index=True,
        comment="Внешний ключ на родительскую задачу (самоссылка 1:N).",
    )
    parent: Mapped[Optional["TaskModel"]] = relationship(
        "TaskModel",
        remote_side=[id],
        back_populates="sub_tasks",
    )
    sub_tasks: Mapped[list["TaskModel"]] = relationship(
        "TaskModel",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    executors: Mapped[Optional[list["TaskExecutorModel"]]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    project_id: Mapped[Optional[UUID]] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
        comment="Внешний ключ на проект (1:N).",
    )
    project: Mapped[Optional["ProjectModel"]] = relationship(
        back_populates="project_tasks",
    )

    comments: Mapped[list["CommentModel"]] = relationship(
        "CommentModel",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TaskExecutorModel(BaseModel):
    __tablename__ = "task_executors"
    __table_args__ = (PrimaryKeyConstraint("user_id", "task_id"),)

    id: Mapped[None] = mapped_column(
        SQL_UUID(as_uuid=True),
        primary_key=False,
        nullable=True,
        comment="Не используется (для совместимости с BaseModel).",
    )

    #  Main field
    estimate: Mapped[int] = mapped_column(
        Integer, nullable=True, comment="Оценка исполнителя за выполненую задачу"
    )

    user_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="Внешний ключ на пользователя (обязательный, исполнитель).",
    )
    user: Mapped["UserModel"] = relationship(
        back_populates="task_executors",
        lazy="joined",
    )

    task_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=False,
        comment="Внешний ключ на задачу (обязательный, задача исполнителя).",
    )
    task: Mapped["TaskModel"] = relationship(
        back_populates="executors",
        lazy="joined",
    )


class CommentModel(BaseModel):
    __tablename__ = "comments"

    description: Mapped[str] = mapped_column(String(512), nullable=False)

    author_id: Mapped[Optional[UUID]] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="Внешний ключ на автора.",
        index=True,
    )

    task_id: Mapped[Optional[UUID]] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=True,
        comment="Внешний ключ на задачу.",
        index=True,
    )

    author: Mapped[Optional["UserModel"]] = relationship(
        "UserModel", back_populates="comments"
    )

    task: Mapped[Optional["TaskModel"]] = relationship(
        "TaskModel", back_populates="comments"
    )


class MeetingModel(BaseModel, TimeEventMixin):
    __tablename__ = "meetings"

    teams: Mapped[list["TeamModel"]] = relationship(
        secondary="meeting_teams",
        back_populates="meetings",
        lazy="selectin",
        comment="Команды, участвующие во встрече.",
    )

    participants: Mapped[list["UserModel"]] = relationship(
        secondary="meeting_participants",
        back_populates="meetings",
        lazy="selectin",
        comment="Индивидуальные участники встречи.",
    )


class EventModel(BaseModel, TimeEventMixin):
    __tablename__ = "events"


def check_time_range_ddl(table_name: str) -> DDL:
    """
    Генерирует SQL-триггер для проверки start_datetime < end_datetime.

    Пример для таблицы events:
        CREATE OR REPLACE FUNCTION check_events_time_range()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.end_datetime <= NEW.start_datetime THEN
                RAISE EXCEPTION 'end_datetime должен быть строго после start_datetime';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trig_events_time_range ON events;
        CREATE TRIGGER trig_events_time_range
            BEFORE INSERT OR UPDATE ON events
            FOR EACH ROW
            EXECUTE FUNCTION check_events_time_range();
    """
    func_name = f"check_{table_name}_time_range"
    trigger_name = f"trig_{table_name}_time_range"

    return DDL(f"""
        CREATE OR REPLACE FUNCTION {func_name}()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.end_datetime <= NEW.start_datetime THEN
                RAISE EXCEPTION 'end_datetime должен быть строго после start_datetime';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};
        CREATE TRIGGER {trigger_name}
            BEFORE INSERT OR UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION {func_name}();
    """)


# === Применение триггеров ===
event.listen(EventModel.__table__, "before_create", check_time_range_ddl("events"))
event.listen(MeetingModel.__table__, "before_create", check_time_range_ddl("meetings"))
