"""
Пакет административной панели (SQLAdmin) для BMA.

Назначение:
    Предоставляет защищённую админ-панель для управления сущностями системы
    через веб-интерфейс SQLAdmin (на базе FastAPI).

    Поддерживает CRUD-операции для всех ORM-моделей:
    - Пользователи (UserModel) с маскированием паролей.
    - Команды (TeamModel).
    - Проекты (ProjectModel).
    - Задачи (TaskModel) с иерархией (родитель/подзадачи).
    - Исполнители задач (TaskExecutorModel).
    - Встречи (MeetingModel) с участниками и командами.
    - События (EventModel).
    - Комментарии (CommentModel).

Архитектура:
    - admin_views.py: эндпоинты аутентификации (login/logout) и регистрация администраторов.
    - admin.py: инициализация SQLAdmin (SQLAdminViewSet), подключение к FastAPI-приложению.
    - models.py: SQLAlchemy-админ-модели (AdminModel) с кастомными полями и формой.
    - authentication.py: аутентификация админа через сессию (SQLAdminAPIAuthentication).

Ключевые принципы:
    - DRY: параметры подключения админа вынесены в конфигурацию.
    - KISS: простые эндпоинты без излишней абстракции.
    - Безопасность: маскирование чувствительных полей, проверка роли admin, CSRF-защита.
    - Dependency Injection: engine и session_maker передаются через app.state.

Ограничения:
    - Админ-панель доступна только для пользователей с ролью "admin".
    - Пароли пользователей отображаются в виде «********» и не редактируются через админку.
    - Требуется залогиниться через /admin/login для доступа к панели.

Примеры:
    # Добавление в main.py:
    from app.src.api.admin import admin_view_set

    admin_view_set.setup(app, engine, session_maker, secret_key="your-secret")
    app.include_router(admin_view_set.admin.urls)
"""

from __future__ import annotations
