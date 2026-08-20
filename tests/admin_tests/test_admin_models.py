import pytest
from typing import List, Dict
from unittest.mock import MagicMock, patch

from sqladmin import ModelView

# Импортируем тестируемые модели
from app.src.api.admin.models import (
    UserModelView,
    TeamModelView,
    ProjectModelView,
    TaskModelView,
    TaskExecutorModelView,
    CommentModelView,
    MeetingModelView,
    EventModelView,
    ADMIN_VIEW_LIST,
)
from app.src.dal.database.models import UserModel


class TestModelViewConfiguration:
    """Базовые тесты конфигурации ModelView классов."""

    @pytest.mark.parametrize("view_class", [
        UserModelView,
        TeamModelView,
        ProjectModelView,
        TaskModelView,
        TaskExecutorModelView,
        CommentModelView,
        MeetingModelView,
        EventModelView,
    ])
    def test_has_required_attributes(self, view_class: type[ModelView]):
        """Тест того, что у каждой модели есть обязательные атрибуты."""
        # Проверяем наличие имен
        assert hasattr(view_class, 'name'), f"{view_class.__name__} не имеет атрибута 'name'"
        assert hasattr(view_class, 'name_plural'), f"{view_class.__name__} не имеет атрибута 'name_plural'"
        assert hasattr(view_class, 'column_list'), f"{view_class.__name__} не имеет атрибута 'column_list'"
        
        # Имена должны быть строками и не пустыми
        assert isinstance(view_class.name, str) and len(view_class.name) > 0
        assert isinstance(view_class.name_plural, str) and len(view_class.name_plural) > 0
        
        # column_list должен быть списком строк
        assert isinstance(view_class.column_list, list)
        for item in view_class.column_list:
            assert isinstance(item, str)

    def test_admin_view_list_completeness(self):
        """Тест того, что ADMIN_VIEW_LIST содержит все определенные представления."""
        expected_views = [
            UserModelView,
            TeamModelView,
            ProjectModelView,
            TaskModelView,
            TaskExecutorModelView,
            CommentModelView,
            MeetingModelView,
            EventModelView,
        ]
        
        view_classes_in_list = [view for view in ADMIN_VIEW_LIST]
        
        # Проверка количества
        assert len(view_classes_in_list) == len(expected_views), \
            f"Ожидалось {len(expected_views)} представлений, найдено {len(view_classes_in_list)}"
            
        # Проверка наличия каждого класса
        for expected_view in expected_views:
            assert expected_view in view_classes_in_list, \
                f"Представление {expected_view.__name__} отсутствует в ADMIN_VIEW_LIST"


class TestUserModelView:
    """Специфичные тесты для UserModelView."""

    def test_form_excludes_sensitive_fields(self):
        """Тест, что чувствительные поля исключены из формы."""
        expected_excluded = [
            "id", "created_at", "updated_at", 
            "refresh_token_hash", "hashed_password",
            "task_executors", "comments", "meetings", "team"
        ]
        
        for field in expected_excluded:
            assert field in UserModelView.form_excluded_fields, \
                f"Поле '{field}' должно быть исключено из формы, но его нет в form_excluded_fields"

    def test_column_formatters_detail_masks_password(self):
        """Тест форматтера для маскирования пароля."""
        formatter_func = UserModelView.column_formatters_detail.get("hashed_password")
        assert formatter_func is not None, "Форматтер для hashed_password отсутствует"
        
        # Мокаем модель с паролем
        mock_user = MagicMock(spec=UserModel)
        mock_user.hashed_password = "super_secret_hash"
        
        # Проверяем форматирование
        result = formatter_func(mock_user, "hashed_password")
        assert result == "********", f"Пароль должен маскироваться, но получено: {result}"
        
        # Проверяем, что None не вызывает ошибку и возвращает пустую строку или None
        mock_user_none = MagicMock(spec=UserModel)
        mock_user_none.hashed_password = None
        result_none = formatter_func(mock_user_none, "hashed_password")
        assert result_none == "", f"При None должен возвращаться пустая строка, но получено: {result_none}"
        
    @pytest.mark.asyncio
    async def test_on_model_change_hashes_password_on_create(self):
        """Тест, что при создании пользователя пароль хешируется."""
        view = UserModelView()
        
        # Создаем моковую модель
        mock_model = MagicMock(spec=UserModel)
        
        # Данные формы
        data = {"username": "testuser", "email": "test@example.com"}
        
        # Мокаем метод хеширования
        mock_hash = "mocked_hash_value"
        view._hash_password = MagicMock(return_value=mock_hash)
        
        # Вызываем хук
        await view.on_model_change(data, mock_model, is_created=True)
        
        # Проверяем, что хэш был установлен
        assert hasattr(mock_model, 'hashed_password')
        assert mock_model.hashed_password == mock_hash
        
        # Проверяем, что метод хеширования был вызван с правильным паролем
        view._hash_password.assert_called_once_with("admin")
            
    @pytest.mark.asyncio
    async def test_on_model_change_does_not_hash_on_update(self):
        """Тест, что при обновлении пользователя пароль НЕ меняется."""
        view = UserModelView()
        
        mock_model = MagicMock(spec=UserModel)
        mock_model.hashed_password = "original_hash"
        
        data = {"username": "updateduser"}
        
        await view.on_model_change(data, mock_model, is_created=False)
        
        # Пароль должен остаться прежним
        assert mock_model.hashed_password == "original_hash"


class TestTaskModelView:
    """Тесты для TaskModelView."""

    def test_relation_loading_enabled(self):
        """Тест, что для задач включена загрузка отношений."""
        assert hasattr(TaskModelView, 'column_list_select_relations')
        assert TaskModelView.column_list_select_relations is True

    def test_form_columns_are_subset_of_details(self):
        """Тест, что поля в форме являются подмножеством детальных полей."""
        # Это упрощенная проверка: все поля в form_columns должны быть полезными
        # В реальном проекте можно проверить, что они существуют в модели
        assert "name" in TaskModelView.form_columns
        assert "project_id" in TaskModelView.form_columns


class TestTeamModelView:
    """Тесты для TeamModelView."""

    def test_basic_config(self):
        """Базовая проверка конфигурации команды."""
        assert TeamModelView.name == "Команда"
        assert TeamModelView.name_plural == "Команды"
        assert "name" in TeamModelView.form_columns