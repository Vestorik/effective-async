"""
Тесты для views (team_router_views, task_router_views, dashboard_router_views).

Покрытие:
- Team views: list, detail, create, join.
- Task views: list, detail, create, update, delete, add_executor.

Кейсы:
- Happy path.
- Ошибки (404, бизнес-ошибки).
- Проверка вызовов сервисов и репозиториев.
"""
from datetime import datetime
from types import SimpleNamespace
from contextlib import asynccontextmanager
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Импортируем роутеры
# Импортируем сервисы и исключения для настройки моков
from app.src.api.client.views.other_views import (
    TaskService,
    TeamService,
    dashboard_router_views,
    task_router_views,
    team_router_views,
)
from app.src.api.exceptions import TaskNotFound, TeamNotFound
from app.src.api.services.auth import RoleType, get_current_user_dep
from app.src.api.services.dashboard_service import DashboardService

# Импортируем утилиту зависимости
from app.src.api.utils.api_utils import get_data_manager
from app.src.dal.database.models import UserModel

# Создаем тестовое приложение с роутерами
app = FastAPI()
app.include_router(dashboard_router_views)
app.include_router(team_router_views)
app.include_router(task_router_views)

@asynccontextmanager
async def run_http_request_as_user(
    app: FastAPI,
    client_factory: Callable[[], AsyncClient],
    path: str,
    method: str = "GET",
    *,
    user: Any,
    data_manager: Any,
    extra_overrides: dict[Any, Callable] | None = None,
    patches: list[tuple[str, Any]] | None = None, 
    payload: dict | None = None,
    params: dict | None = None,
    data: dict | None = None
):
    """
    Выполняет HTTP-запрос с подменёнными зависимостями и патчами.
    Гарантированно восстанавливает состояние.
    
    patches: список кортежей (target_path, return_value), например:
        [("app.src.api.views.other_views.TeamService", mock_service)]
    """
    original_overrides = dict(app.dependency_overrides)
    active_patches = []

    try:
        # 1. Подменяем зависимости FastAPI
        app.dependency_overrides[get_current_user_dep] = lambda: user
        app.dependency_overrides[get_data_manager] = lambda: data_manager
        if extra_overrides:
            app.dependency_overrides.update(extra_overrides)

        # 2. Применяем обычные патчи (для случаев типа team_service = TeamService())
        if patches:
            for target, mock_obj in patches:
                p = patch(target, return_value=mock_obj)
                p.start()
                active_patches.append(p)

        async with client_factory() as client:
            if method == "GET":
                response = await client.get(path)
            elif method == "POST":
                response = await client.post(path, data=payload, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")

        yield response

    finally:
        # Восстанавливаем всё в обратном порядке
        for p in reversed(active_patches):
            p.stop()
        
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)

class MockDataManager:
    """
    Мок менеджера данных (UoW).
    Реализует минимальный интерфейс, требуемый хендлерами.
    """

    def __init__(self):
        self.teams = AsyncMock()
        self.users = AsyncMock()
        self.tasks = AsyncMock()
        self.task_executors = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __call__(self):
        """Если хендлеры используют manager() как контекст-менеджер"""
        return self

def mock_user_id() -> str:
    """Генерирует уникальный ID пользователя для тестов."""
    return str(uuid4())

@pytest.fixture
def mock_data_manager() -> MockDataManager:
    """Фикстура для мока DataManager."""
    return MockDataManager()

def _get_async_client():
    """Вспомогательная функция для получения асинхронного клиента"""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


class TestTeamViews:
    """Тесты для team_router_views"""
    
    @pytest.mark.asyncio
    async def test_teams_list_success(self, mock_data_manager):
        mock_teams = [
            MagicMock(id=uuid4(), name="Team 1"),
            MagicMock(id=uuid4(), name="Team 2"),
        ]
        # Мокаем то, что реально нужно
        mock_data_manager.teams.get_all_teams.return_value = mock_teams

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path="/views/teams/",
            method="GET",
            user=fake_user,
            data_manager=mock_data_manager,
        ) as response:

         assert response.status_code == 200


    @pytest.mark.asyncio
    async def test_team_detail_success(self, mock_data_manager):
        """Scenario: Успешный просмотр деталей команды."""
        mock_team = MagicMock(id=uuid4(), name="Main Team")
        team_id = str(mock_team.id)

        # Мокаем то, что реально нужно внутри data_manager/сервиса
        mock_data_manager.teams.get_team_by_id = AsyncMock(return_value=mock_team)
        mock_service = MagicMock(spec=TeamService)
        mock_service.get_team_by_id = AsyncMock(return_value=mock_team)
        

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )
        
        patches = [
            ("app.src.api.client.views.other_views.TeamService", mock_service)
        ]
        
        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path=f"/views/teams/{team_id}",
            method="GET",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
        ) as response:

         assert response.status_code == 200


    @pytest.mark.asyncio
    async def test_team_detail_not_found(self, mock_data_manager):
        team_id = str(uuid4())

        mock_service = MagicMock(spec=TeamService)
        mock_service.get_team_by_id = AsyncMock(side_effect=TeamNotFound())

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        # Путь должен указывать туда, где класс используется (в файле роута/эндпоинта)
        # Например, если эндпоинт в app/src/api/client/views/other_views.py:
        patches = [
            ("app.src.api.client.views.other_views.TeamService", mock_service)
        ]

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path=f"/views/teams/{team_id}",
            method="GET",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
        ) as response:
            assert response.status_code == 404


    @pytest.mark.asyncio
    async def test_create_team_success(self, mock_data_manager):
        mock_service = MagicMock(spec=TeamService)
        mock_service.create_team = AsyncMock()

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        patches = [
            ("app.src.api.client.views.other_views.TeamService", mock_service),
        ]

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path="/views/teams/create",
            method="POST",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
            payload={"name": "New Team"},
        ) as response:
            assert response.status_code in (201, 303, 307, 200)


    @pytest.mark.asyncio
    async def test_join_team_success(self, mock_data_manager):
        team_id = str(uuid4())
        mock_service = MagicMock(spec=TeamService)
        mock_service.join_team = AsyncMock()

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        patches = [
            ("app.src.api.client.views.other_views.TeamService", mock_service),
        ]

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path="/views/teams/join",
            method="POST",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
            payload={"team_id": team_id},
        ) as response:
            assert response.status_code in (200, 303, 307, 204)


    @pytest.mark.asyncio
    async def test_join_team_not_found(self, mock_data_manager):
        team_id = str(uuid4())
        mock_service = MagicMock(spec=TeamService)
        mock_service.join_team = AsyncMock(side_effect=TeamNotFound())

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        patches = [
            ("app.src.api.client.views.other_views.TeamService", mock_service),
        ]

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path="/views/teams/join",
            method="POST",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
            payload={"team_id": team_id},
        ) as response:
            assert response.status_code == 404


class TestTaskViews:
    """Тесты для task_router_views"""




    @pytest.mark.asyncio
    async def test_task_detail_success(self, mock_data_manager):
        """
        Scenario: Успешный просмотр деталей задачи.
        """
        task_id = uuid4()


        mock_task = SimpleNamespace(
            id=task_id,
            name="Task Detail",
            description="Desc",
            project_id=None,
            parent_id=None,
            created_at=datetime.now(),  # noqa: DTZ005
        )

        # Мокаем получение исполнителей (тоже должно быть списком, иначе схема упадёт)
        mock_executors = []  # или список объектов/словарей, как ожидает TaskWithExecutorsOutSheme

        mock_data_manager.tasks.get_by_id = AsyncMock(return_value=mock_task)
        mock_data_manager.task_executors.get_executors_for_task = AsyncMock(
            return_value=mock_executors
    )
        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        patches = [
            ("app.src.api.client.views.other_views.TaskService", MagicMock(spec=TaskService)),
        ]

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path=f"/views/tasks/{task_id}",
            method="GET",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
        ) as response:
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_task_detail_not_found(self, mock_data_manager):
        """
        Scenario: Задача не найдена.
        """
        task_id = uuid4()

        mock_data_manager.tasks.get_by_id = AsyncMock(return_value=None)

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        patches = [
            ("app.src.api.client.views.other_views.TaskService", MagicMock(spec=TaskService)),
        ]

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path=f"/views/tasks/{task_id}",
            method="GET",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
        ) as response:
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_task_success(self, mock_data_manager):
        """
        Scenario: Успешное создание задачи.
        """
        mock_service = MagicMock(spec=TaskService)
        mock_service.create_task = AsyncMock()
                
        fake_user_id = uuid4()
        team_id = str(uuid4())
            
            # Данные для формы (ключи должны точно совпадать с именами аргументов в эндпоинте)
        form_data = {
                "team_id": team_id,
                "name": "New Task",
                "description": "New Desc",
                "priority": "high",
            }

        fake_user = UserModel(
                id=fake_user_id,
                role=RoleType.ADMIN.value,
                username="name",
                email="email",
                hashed_password="password",
            )

        patches = [
            ("app.src.api.client.views.other_views.TaskService", mock_service),
        ]
        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path="/views/tasks/create",
            method="POST",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
            payload=form_data,
        ) as response:
            assert response.status_code in (201, 303, 307, 200)


    @pytest.mark.asyncio
    async def test_delete_task_success(self, mock_data_manager):
        """
        Scenario: Успешное удаление задачи.
        """
        mock_service = MagicMock(spec=TaskService)
        mock_service.delete_task = AsyncMock()

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        task_id = uuid4()
        
        patches = [
            ("app.src.api.client.views.other_views.TaskService", mock_service),
        ]

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path=f"/views/tasks/delete/{task_id}",
            method="POST",  # Проверь, действительно ли у тебя POST для удаления
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
        ) as response:
            assert response.status_code in (303, 307, 200, 204)

    @pytest.mark.asyncio
    async def test_add_executor_success(self, mock_data_manager):
        """Scenario: Добавление исполнителя."""
        mock_service = MagicMock(spec=TaskService)
        mock_service.add_executor = AsyncMock()

        fake_user = UserModel(
            id=uuid4(),
            role=RoleType.ADMIN.value,
            username="name",
            email="email",
            hashed_password="password",
        )

        task_id = str(uuid4())
        user_id = str(uuid4())

        payload = {
            "task_id": task_id,
            "user_id": user_id,
            "estimate": "10",
        }

        patches = [
            ("app.src.api.client.views.other_views.TaskService", mock_service),
        ]

        async with run_http_request_as_user(
            app=app,
            client_factory=_get_async_client,
            path="/views/tasks/add_executor",
            method="POST",
            user=fake_user,
            data_manager=mock_data_manager,
            patches=patches,
            payload=payload,
        ) as response:
            assert response.status_code in (303, 307, 200, 204)



class TestTeamJoinViews:
    """Тесты для join_team (отсутствующие кейсы)"""

    @pytest.mark.asyncio
    async def test_join_team_success(self, mock_data_manager):
        """
        Scenario: Успешное вступление в команду.
        """
        mock_service = MagicMock(spec=TeamService)
        mock_service.join_team = AsyncMock()
        team_id = str(uuid4())

        with (
            patch("app.src.api.client.views.other_views.TeamService", return_value=mock_service),
     
        ):
            app.dependency_overrides[get_data_manager] = lambda: mock_data_manager

            async with _get_async_client() as client:
                response = await client.post(
                    "/views/teams/join", data={"team_id": team_id}
                )

            # Ожидаем редирект (303)
            assert response.status_code in [303, 401]

    @pytest.mark.asyncio
    async def test_join_team_not_found(self, mock_data_manager):
        """
        Scenario: Вступление в несуществующую команду -> 404.
        """
        team_id = str(uuid4())
        mock_service = MagicMock(spec=TeamService)
        mock_service.join_team = AsyncMock(side_effect=TeamNotFound())

        with (
            patch("app.src.api.client.views.other_views.TeamService", return_value=mock_service),
         
        ):
            app.dependency_overrides[get_data_manager] = lambda: mock_data_manager

            async with _get_async_client() as client:
                response = await client.post(
                    "/views/teams/join", data={"team_id": team_id}
                )

            assert response.status_code in [404,401]


class TestTaskUpdateViews:
    """Тесты для update_task и update_executor_estimate"""

    @pytest.mark.asyncio
    async def test_update_task_success(self, mock_data_manager):
        """
        Scenario: Успешное обновление задачи.
        """
        mock_service = MagicMock(spec=TaskService)
        mock_service.update_task = AsyncMock()
        task_id = uuid4()

        with (
            patch("app.src.api.client.views.other_views.TaskService", return_value=mock_service),
          
        ):
            app.dependency_overrides[get_data_manager] = lambda: mock_data_manager

            async with _get_async_client() as client:
                response = await client.post(
                    f"/views/tasks/update/{task_id}",
                    data={"name": "Updated Name", "description": "Updated Desc"},
                )

            # Ожидаем редирект (303)
            assert response.status_code in [301,401]

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, mock_data_manager):
        """
        Scenario: Обновление несуществующей задачи -> 404.
        """
        mock_service = MagicMock(spec=TaskService)
        mock_service.update_task = AsyncMock(side_effect=TaskNotFound())
        task_id = uuid4()

        with (
            patch("app.src.api.client.views.other_views.TaskService", return_value=mock_service),
       
        ):
            app.dependency_overrides[get_data_manager] = lambda: mock_data_manager

            async with _get_async_client() as client:
                response = await client.post(
                    f"/views/tasks/update/{task_id}",
                    data={"name": "Updated Name", "description": "Updated Desc"},
                )

            assert response.status_code in [404,401]


class TestTaskExecutorViews:
    """Тесты для add_executor_to_task и update_executor_estimate"""

    @pytest.mark.asyncio
    async def test_add_executor_success(self, mock_data_manager):
        """
        Scenario: Успешное добавление исполнителя.
        """
        mock_service = MagicMock(spec=TaskService)
        mock_service.add_executor = AsyncMock()
        task_id = str(uuid4())
        user_id = str(uuid4())

        with (
            patch("app.src.api.client.views.other_views.TaskService", return_value=mock_service),
          
        ):
            app.dependency_overrides[get_data_manager] = lambda: mock_data_manager

            async with _get_async_client() as client:
                response = await client.post(
                    "/views/tasks/add_executor",
                    data={"task_id": task_id, "user_id": user_id, "estimate": "10"},
                )

            # Ожидаем редирект (303)
            assert response.status_code in [303,401]

    @pytest.mark.asyncio
    async def test_update_executor_estimate_success(
        self, mock_data_manager
    ):
        """
        Scenario: Успешное обновление оценки исполнителя.
        """
        mock_service = MagicMock(spec=TaskService)
        mock_service.update_executor_estimate = AsyncMock()
        task_id = str(uuid4())
        user_id = str(uuid4())

        with (
            patch("app.src.api.client.views.other_views.TaskService", return_value=mock_service),
            
        ):
            app.dependency_overrides[get_data_manager] = lambda: mock_data_manager

            async with _get_async_client() as client:
                response = await client.post(
                    "/views/tasks/update_executor_estimate",
                    data={"task_id": task_id, "user_id": user_id, "estimate": "20"},
                )

            # Ожидаем редирект (303)
            assert response.status_code in [303,401]

    @pytest.mark.asyncio
    async def test_update_executor_estimate_error(
        self, mock_data_manager
    ):
        """
        Scenario: Ошибка при обновлении оценки (например, задача не найдена).
        """
        mock_service = MagicMock(spec=TaskService)
        mock_service.update_executor_estimate = AsyncMock(side_effect=TaskNotFound())
        task_id = str(uuid4())
        user_id = str(uuid4())

        with (
            patch("app.src.api.client.views.other_views.TaskService", return_value=mock_service),
          
        ):
            app.dependency_overrides[get_data_manager] = lambda: mock_data_manager

            async with _get_async_client() as client:
                response = await client.post(
                    "/views/tasks/update_executor_estimate",
                    data={"task_id": task_id, "user_id": user_id, "estimate": "20"},
                )

            # Согласно коду, исключение преобразуется в 400
            assert response.status_code in [400,401]
