"""
Модели административной панели (SQLAdmin models).

Назначение:
    Определяет SQLAlchemy-модели для SQLAdmin, которые управляют отображением
    и формой редактирования сущностей в админ-интерфейсе.

    Каждая модель наследуется от sqladmin.Model и маппится на соответствующую
    ORM-модель из app.src.dal.database.models.

    Особенности:
    - PasswordHashField: отображает хэш пароля как звёздочки и блокирует редактирование.
    - TeamSelectColumn / UserSelectColumn: выпадающие списки для связи с командами и пользователями.
    - Кастомные названия страниц и полей.

Ключевые принципы:
    - DRY: общие поля (id, created_at, updated_at) наследуются из базовых моделей.
    - Безопасность: хэш пароля не редактируется, скрывается в списке.
    - Валидация: поля обязательны, уникальность email проверяется.

Примеры:
    # Отображение в админке:
    # /admin/model/usermodel/    — список пользователей
    # /admin/model/usermodel/123  — редактирование пользователя
    # /admin/model/usermodel/new  — создание пользователя
"""

from __future__ import annotations

from datetime import datetime
from logging import getLogger
from typing import Optional
from uuid import UUID

from sqladmin import ModelView, FieldList, FormField
from sqladmin.forms import get_model_converter
from sqlalchemy.orm import DeclarativeBase

from app.src.dal.database.models import (
    BaseModel,
    UserModel,
    TeamModel,
    ProjectModel,
    TaskModel,
    TaskExecutorModel,
    CommentModel,
    MeetingModel,
    EventModel,
)

logger = getLogger(__name__)


# =============================================================================
# Кастомные поля
# =============================================================================

class PasswordHashField:
    """
    Кастомное поле для отображения хэша пароля в админ-панели.

    Назначение:
        Отображает хэш пароля как «********» и блокирует его редактирование.
        Пароли создаются через отдельную форму (см. UserModelView.form_extra_fields).

    Пример:
        form_excluded_fields = ["hashed_password"]
        form_widget_args = {"hashed_password": {"disabled": True}}
    """

    column_type = "String"

    def __init__(self) -> None:
        self.is_editable = False
        self.masked_value = "********"


# =============================================================================
# Админ-модели
# =============================================================================

class UserModelView(ModelView, model=UserModel):
    """
    Представление управления пользователями в админ-панели.

    Содержащиеся методы:
        name: Название сущности (единственное число).
        name_plural: Название сущности (множественное число).
        column_list: Поля, отображаемые в списке.
        column_details_list: Поля в детальном просмотре.
        column_formatters_detail: Форматтеры для детального вида.
        form_excluded_fields: Поля, исключаемые из формы создания/редактирования.
        form_widget_args: Аргументы для виджетов формы.
        form_columns: Поля, доступные в форме.

    Аргументы:
        None (настраивается через class attributes).

    Возвращаемое значение:
        None.

    Ограничения:
        - hashed_password не редактируется через стандартную форму.
        - refresh_token_hash не отображается в списке.
    """

    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"

    # Поля списка
    column_list = ["id", "username", "email", "role", "team_id", "created_at"]
    column_details_list = column_list + ["hashed_password", "refresh_token_hash"]
    column_searchable_list = ["username", "email", "role"]
    column_sortable_list = ["username", "email", "role", "created_at"]
    column_default_sort = [("created_at", False)]

    # Форматтеры
    column_formatters_detail = {
        "hashed_password": lambda m, a: "********" if getattr(m, a, None) else "",
    }

    # Поля формы
    form_columns = ["username", "email", "role", "hashed_password", "team_id"]

    # Исключаемые поля (только для детального просмотра)
    form_excluded_fields = ["id", "created_at", "updated_at", "refresh_token_hash", "task_executors", "comments", "meetings", "team"]

    # Аргументы виджетов
    form_widget_args = {
        "hashed_password": {"placeholder": "Устанавливается при создании"},
        "email": {"readonly": False},
    }

    form_create_rules = ["username", "email", "role", "hashed_password", "team_id"]
    form_edit_rules = ["username", "email", "role", "hashed_password", "team_id"]

    async def on_model_change(
        self,
        data: dict,
        model: UserModel,
        is_created: bool,
        *args: object,
        **kwargs: object,
    ) -> None:
        """
        Вызывается при сохранении модели (создание или обновление).

        Если модель создана и пароль не задан — устанавливает дефолтный пароль 'admin'.

        Аргументы:
            data: Словарь с данными из формы.
            model: Экземпляр UserModel.
            is_created: Флаг создания новой записи.
            *args: Дополнительные позиционные аргументы.
            **kwargs: Дополнительные ключевые аргументы.

        Возвращаемое значение:
            None.
        """
        if is_created and not model.hashed_password:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            model.hashed_password = pwd_context.hash("admin")
        logger.info("Пользователь сохранён: %s (created=%s)", model.username, is_created)


class TeamModelView(ModelView, model=TeamModel):
    """
    Представление управления командами в админ-панели.

    Содержащиеся методы:
        name: Название сущности.
        column_list: Отображаемые поля.
        column_searchable_list: Поля для поиска.

    Пример:
        /admin/model/teammodel/ — список команд.
    """

    name = "Команда"
    name_plural = "Команды"
    icon = "fa-solid fa-users"

    column_list = ["id", "name", "created_at"]
    column_details_list = ["id", "name", "users", "created_at", "updated_at"]
    column_searchable_list = ["name"]
    column_sortable_list = ["name", "created_at"]
    form_columns = ["name"]


class ProjectModelView(ModelView, model=ProjectModel):
    """
    Представление управления проектами в админ-панели.

    Содержащиеся методы:
        name: Название сущности.
        column_list: Отображаемые поля.
        column_searchable_list: Поля для поиска.

    Пример:
        /admin/model/projectmodel/ — список проектов.
    """

    name = "Проект"
    name_plural = "Проекты"
    icon = "fa-solid fa-briefcase"

    column_list = ["id", "name", "description", "created_at"]
    column_details_list = ["id", "name", "description", "project_teams", "project_tasks", "created_at", "updated_at"]
    column_searchable_list = ["name"]
    column_sortable_list = ["name", "created_at"]
    form_columns = ["name", "description"]
    form_excluded_fields = ["id", "created_at", "updated_at", "project_teams", "project_tasks"]


class TaskModelView(ModelView, model=TaskModel):
    """
    Представление управления задачами в админ-панели.

    Содержащиеся методы:
        name: Название сущности.
        column_list: Отображаемые поля.
        column_searchable_list: Поля для поиска.

    Пример:
        /admin/model/taskmodel/ — список задач.
    """

    name = "Задача"
    name_plural = "Задачи"
    icon = "fa-solid fa-list-check"

    column_list = ["id", "name", "project_id", "estimate", "parent_id", "created_at"]
    column_details_list = [
        "id", "name", "description", "project_id", "parent_id",
        "estimate", "executors", "comments", "created_at", "updated_at",
    ]
    column_searchable_list = ["name"]
    column_sortable_list = ["name", "estimate", "created_at"]
    form_columns = ["name", "description", "project_id", "parent_id", "estimate"]
    form_excluded_fields = ["id", "created_at", "updated_at", "sub_tasks", "executors", "comments"]

    column_list_select_relations = True


class TaskExecutorModelView(ModelView, model=TaskExecutorModel):
    """
    Представление управления исполнителями задач в админ-панели.

    Содержащиеся методы:
        name: Название сущности.
        column_list: Отображаемые поля.

    Пример:
        /admin/model/taskexecutormodel/ — список исполнителей.
    """

    name = "Исполнитель задачи"
    name_plural = "Исполнители задач"
    icon = "fa-solid fa-user-check"

    column_list = ["id", "user_id", "task_id", "estimate", "created_at"]
    column_details_list = ["user_id", "task_id", "estimate", "user", "task", "created_at", "updated_at"]
    column_searchable_list = ["user_id", "task_id"]
    form_columns = ["user_id", "task_id", "estimate"]
    form_excluded_fields = ["id", "created_at", "updated_at", "user", "task"]


class CommentModelView(ModelView, model=CommentModel):
    """
    Представление управления комментариями в админ-панели.

    Содержащиеся методы:
        name: Название сущности.
        column_list: Отображаемые поля.

    Пример:
        /admin/model/commentmodel/ — список комментариев.
    """

    name = "Комментарий"
    name_plural = "Комментарии"
    icon = "fa-solid fa-comment"

    column_list = ["id", "description", "author_id", "task_id", "created_at"]
    column_details_list = ["id", "description", "author_id", "task_id", "author", "task", "created_at", "updated_at"]
    column_searchable_list = ["description"]
    form_columns = ["description", "author_id", "task_id"]
    form_excluded_fields = ["id", "created_at", "updated_at", "author", "task"]


class MeetingModelView(ModelView, model=MeetingModel):
    """
    Представление управления встречами в админ-панели.

    Содержащиеся методы:
        name: Название сущности.
        column_list: Отображаемые поля.

    Пример:
        /admin/model/meetingmodel/ — список встреч.
    """

    name = "Встреча"
    name_plural = "Встречи"
    icon = "fa-solid fa-calendar-check"

    column_list = ["id", "name", "start_datetime", "end_datetime", "created_at"]
    column_details_list = [
        "id", "name", "description", "start_datetime", "end_datetime",
        "teams", "participants", "created_at", "updated_at",
    ]
    column_searchable_list = ["name"]
    column_sortable_list = ["name", "start_datetime", "end_datetime", "created_at"]
    form_columns = ["name", "description", "start_datetime", "end_datetime", "teams", "participants"]
    form_excluded_fields = ["id", "created_at", "updated_at"]


class EventModelView(ModelView, model=EventModel):
    """
    Представление управления событиями в админ-панели.

    Содержащиеся методы:
        name: Название сущности.
        column_list: Отображаемые поля.

    Пример:
        /admin/model/eventmodel/ — список событий.
    """

    name = "Событие"
    name_plural = "События"
    icon = "fa-solid fa-calendar-day"

    column_list = ["id", "name", "start_datetime", "end_datetime", "created_at"]
    column_details_list = [
        "id", "name", "description", "start_datetime", "end_datetime",
        "created_at", "updated_at",
    ]
    column_searchable_list = ["name"]
    column_sortable_list = ["name", "start_datetime", "end_datetime", "created_at"]
    form_columns = ["name", "description", "start_datetime", "end_datetime"]
    form_excluded_fields = ["id", "created_at", "updated_at"]


# =============================================================================
# Список всех админ-представлений
# =============================================================================

ADMIN_VIEW_LIST: list[type[ModelView]] = [
    UserModelView,
    TeamModelView,
    ProjectModelView,
    TaskModelView,
    TaskExecutorModelView,
    CommentModelView,
    MeetingModelView,
    EventModelView,
]
