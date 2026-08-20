import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.exceptions import HTTPException

from app.src.api.handlers.task_handlers import (
    get_task_by_id,
    get_team_tasks,
    create_task,
    update_task,
    delete_task,
    add_executor_to_task,
    update_executor_estimate,
)
from app.src.api.shems import TaskCreate, TaskUpdateSheme, AddExecutor
from app.src.api.exceptions import TaskNotFound, TeamNotFound
import app.src.api.handlers.task_handlers as mod


class TestTasksRoutes:
    @pytest.fixture
    def mocks(self):
        """Базовые моки для DataManager, UOW и кэшированного UOW."""
        data_manager = MagicMock()
        uow = MagicMock()
        data_manager.return_value.__aenter__.return_value = uow
        uow.tasks = MagicMock()
        uow.task_executors = MagicMock()
        uow.teams = MagicMock()

        # Кэшированный UOW (нужен для get_* с кэшем)
        cuow = MagicMock()
        data_manager.cache.return_value.__aenter__.return_value = cuow
        cuow.tasks = MagicMock()

        return {
            "data_manager": data_manager,
            "uow": uow,
            "cuow": cuow,
        }

    @pytest.fixture
    def patch_service(self):
        """Подменяет TaskService в модуле и гарантирует возврат старого класса после теста."""
        old_TaskService = mod.TaskService
        mock_service = AsyncMock()

        def teardown():
            mod.TaskService = old_TaskService

        yield mock_service
        teardown()

    # --- get_task_by_id (cached) ---

    @pytest.mark.asyncio
    async def test_get_task_by_id_found(self, mocks):
        task_id = uuid.uuid4()
        fake_task = {"id": str(task_id), "name": "test-task"}
        mocks["cuow"].tasks.get_by_id = AsyncMock(return_value=fake_task)

        res = await get_task_by_id(task_id=task_id, data_manager=mocks["data_manager"])
        assert res is not None
        assert res.name == "test-task"

    @pytest.mark.asyncio
    async def test_get_task_by_id_not_found(self, mocks):
        task_id = uuid.uuid4()
        mocks["cuow"].tasks.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as e:
            await get_task_by_id(task_id=task_id, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404

    # --- get_team_tasks (cached, with priority filter) ---

    @pytest.mark.asyncio
    async def test_get_team_tasks_happy(self, mocks):
        team_id = uuid.uuid4()
        priority = "high"
        fake_list = [
            {"id": str(uuid.uuid4()), "name": "t1", "priority": priority},
            {"id": str(uuid.uuid4()), "name": "t2", "priority": priority},
        ]
        mocks["cuow"].tasks.get_tasks_by_team_and_priority = AsyncMock(
            return_value=fake_list
        )

        res = await get_team_tasks(
            team_id=team_id,
            data_manager=mocks["data_manager"],
            priority=priority,
        )
        assert isinstance(res, list)
        assert len(res) == 2

    @pytest.mark.asyncio
    async def test_get_team_tasks_no_priority(self, mocks):
        team_id = uuid.uuid4()
        fake_list = [{"id": str(uuid.uuid4()), "name": "t1"}]
        mocks["cuow"].tasks.get_tasks_by_team_and_priority = AsyncMock(
            return_value=fake_list
        )

        res = await get_team_tasks(
            team_id=team_id,
            data_manager=mocks["data_manager"],
            priority=None,
        )
        assert isinstance(res, list)
        assert len(res) == 1

    # --- create_task (write) ---

    @pytest.mark.asyncio
    async def test_create_task_happy(self, mocks, patch_service):
        team_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = TaskCreate(
            name="new-task",
            description="desc",
            priority="medium",
            parent_id=None,
            executor_ids=[],
        )
        fake_task = {
            "id": str(uuid.uuid4()),
            "name": payload.name,
            "priority": payload.priority,
        }
        patch_service.create_task.return_value = fake_task
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        res = await create_task(
            team_id=team_id,
            task_data=payload,
            user_id=user_id,
            data_manager=mocks["data_manager"],
        )
        assert res is not None

    @pytest.mark.asyncio
    async def test_create_task_team_not_found(self, mocks, patch_service):
        team_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = TaskCreate(name="bad-team", description="d", priority="low")

        patch_service.create_task.side_effect = TeamNotFound()
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        with pytest.raises(HTTPException) as e:
            await create_task(
                team_id=team_id,
                task_data=payload,
                user_id=user_id,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_task_parent_not_found(self, mocks, patch_service):
        team_id = uuid.uuid4()
        user_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        payload = TaskCreate(
            name="bad-parent",
            description="d",
            priority="low",
            parent_id=parent_id,
        )

        patch_service.create_task.side_effect = Exception("не найдена")
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        with pytest.raises(HTTPException) as e:
            await create_task(
                team_id=team_id,
                task_data=payload,
                user_id=user_id,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_task_invalid_priority(self, mocks, patch_service):
        team_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = TaskCreate(name="bad-prio", description="d", priority="superhigh")

        patch_service.create_task.side_effect = Exception("приоритет")
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        with pytest.raises(HTTPException) as e:
            await create_task(
                team_id=team_id,
                task_data=payload,
                user_id=user_id,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 400

    # --- update_task (write) ---

    @pytest.mark.asyncio
    async def test_update_task_happy(self, mocks, patch_service):
        task_id = uuid.uuid4()
        payload = TaskUpdateSheme(name="updated", description="new desc", priority="high")
        fake_task = {
            "id": str(task_id),
            "name": payload.name,
            "priority": payload.priority,
        }
        patch_service.update_task.return_value = fake_task
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        res = await update_task(
            task_id=task_id,
            task_update=payload,
            data_manager=mocks["data_manager"],
        )
        assert res is not None
        assert res.name == payload.name

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()
        payload = TaskUpdateSheme(name="upd", description="d", priority="low")

        patch_service.update_task.side_effect = TaskNotFound()
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        with pytest.raises(HTTPException) as e:
            await update_task(
                task_id=task_id,
                task_update=payload,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    # --- delete_task (write) ---

    @pytest.mark.asyncio
    async def test_delete_task_success(self, mocks, patch_service):
        task_id = uuid.uuid4()
        patch_service.delete_task.return_value = None
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        res = await delete_task(task_id=task_id, data_manager=mocks["data_manager"])
        assert res is None  # FastAPI сам сделает 204

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()

        patch_service.delete_task.side_effect = TaskNotFound()
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        with pytest.raises(HTTPException) as e:
            await delete_task(task_id=task_id, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404

    # --- add_executor_to_task (write) ---

    @pytest.mark.asyncio
    async def test_add_executor_happy(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = AddExecutor(user_id=user_id, estimate=8)
        fake_executor = {
            "task_id": str(task_id),
            "user_id": str(user_id),
            "estimate": 8,
        }
        patch_service.add_executor.return_value = fake_executor
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        res = await add_executor_to_task(
            task_id=task_id,
            executor_data=payload,
            data_manager=mocks["data_manager"],
        )
        assert res is not None
        assert res.user_id == user_id

    @pytest.mark.asyncio
    async def test_add_executor_task_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = AddExecutor(user_id=user_id, estimate=8)

        patch_service.add_executor.side_effect = TaskNotFound()
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        with pytest.raises(HTTPException) as e:
            await add_executor_to_task(
                task_id=task_id,
                executor_data=payload,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_add_executor_conflict(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = AddExecutor(user_id=user_id, estimate=8)

        patch_service.add_executor.side_effect = Exception("уже добавлен")
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        with pytest.raises(HTTPException) as e:
            await add_executor_to_task(
                task_id=task_id,
                executor_data=payload,
                data_manager=mocks["data_manager"],
            )
        # Твой код превращает это в 409
        assert e.value.status_code == 409

    # --- update_executor_estimate (write, with explicit validation) ---

    @pytest.mark.asyncio
    async def test_update_executor_estimate_happy(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        estimate = 12
        fake_executor = {
            "task_id": str(task_id),
            "user_id": str(user_id),
            "estimate": estimate,
        }
        patch_service.update_executor_estimate.return_value = fake_executor
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        res = await update_executor_estimate(
            task_id=task_id,
            user_id=user_id,
            estimate=estimate,
            data_manager=mocks["data_manager"],
        )
        assert res is not None
        assert res.estimate == estimate

    @pytest.mark.asyncio
    async def test_update_executor_estimate_negative(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        estimate = -5

        # Здесь даже не доходим до сервиса: валидация в роуте
        with pytest.raises(HTTPException) as e:
            await update_executor_estimate(
                task_id=task_id,
                user_id=user_id,
                estimate=estimate,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_executor_estimate_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        estimate = 5

        patch_service.update_executor_estimate.side_effect = Exception("не найдена")
        mod.TaskService = lambda: patch_service  # type: ignore[assignment]

        with pytest.raises(HTTPException) as e:
            await update_executor_estimate(
                task_id=task_id,
                user_id=user_id,
                estimate=estimate,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404
