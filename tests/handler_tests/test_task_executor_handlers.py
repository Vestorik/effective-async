import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.exceptions import HTTPException

from app.src.api.handlers.task_executor_handlers import (
    add_executor_to_task,
    remove_executor_from_task,
    update_executor_estimate_handler,
    get_executors_for_task_handler,
    get_tasks_for_user_handler,
)
from app.src.api.shems import AddExecutor
from app.src.api.exceptions import TaskNotFound, UserNotFound
import app.src.api.handlers.task_executor_handlers as mod


class TestTaskExecutorHandlers:
    @pytest.fixture
    def mocks(self):
        """Базовые моки для DataManager, UOW и кэшированного UOW."""
        data_manager = MagicMock()
        uow = MagicMock()
        data_manager.return_value.__aenter__.return_value = uow
        # Репозитории, которые реально используются в этих хендлерах
        uow.tasks = MagicMock()
        uow.task_executors = MagicMock()

        # Кэшированный UOW (нужен для get_* с кэшем)
        cuow = MagicMock()
        data_manager.cache.return_value.__aenter__.return_value = cuow
        cuow.task_executors = MagicMock()

        return {
            "data_manager": data_manager,
            "uow": uow,
            "cuow": cuow,
        }

    @pytest.fixture
    def patch_service(self):
        """Подменяет TaskExecutorService в модуле и гарантирует возврат старого класса после теста."""
        old_TaskExecutorService = mod.TaskExecutorService
        mock_service = AsyncMock()

        def teardown():
            mod.TaskExecutorService = old_TaskExecutorService

        yield mock_service
        teardown()

    # --- add_executor_to_task ---

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
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        res = await add_executor_to_task(
            task_id=task_id,
            executor_data=payload,
            data_manager=mocks["data_manager"],
        )
        assert res is not None


    @pytest.mark.asyncio
    async def test_add_executor_task_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = AddExecutor(user_id=user_id, estimate=8)

        patch_service.add_executor.side_effect = TaskNotFound()
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await add_executor_to_task(
                task_id=task_id,
                executor_data=payload,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_add_executor_user_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = AddExecutor(user_id=user_id, estimate=8)

        patch_service.add_executor.side_effect = UserNotFound()
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await add_executor_to_task(
                task_id=task_id,
                executor_data=payload,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_add_executor_conflict_already_added(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = AddExecutor(user_id=user_id, estimate=8)

        patch_service.add_executor.side_effect = Exception("уже добавлен")
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await add_executor_to_task(
                task_id=task_id,
                executor_data=payload,
                data_manager=mocks["data_manager"],
            )
        # Твой код превращает это в 409
        assert e.value.status_code == 409

    # --- remove_executor_from_task ---

    @pytest.mark.asyncio
    async def test_remove_executor_success(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()

        patch_service.remove_executor.return_value = None
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        res = await remove_executor_from_task(
            task_id=task_id,
            user_id=user_id,
            data_manager=mocks["data_manager"],
        )
        assert res is None  # FastAPI сам сделает 204

    @pytest.mark.asyncio
    async def test_remove_executor_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()

        patch_service.remove_executor.side_effect = Exception("не найдена")
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await remove_executor_from_task(
                task_id=task_id,
                user_id=user_id,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    # --- update_executor_estimate_handler ---

    @pytest.mark.asyncio
    async def test_update_estimate_happy(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        estimate = 12

        fake_executor = {
            "task_id": str(task_id),
            "user_id": str(user_id),
            "estimate": estimate,
        }
        patch_service.update_estimate.return_value = fake_executor
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        res = await update_executor_estimate_handler(
            task_id=task_id,
            user_id=user_id,
            estimate=estimate,
            data_manager=mocks["data_manager"],
        )
        assert res is not None


    @pytest.mark.asyncio
    async def test_update_estimate_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        estimate = 5

        patch_service.update_estimate.side_effect = Exception("не найдена")
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await update_executor_estimate_handler(
                task_id=task_id,
                user_id=user_id,
                estimate=estimate,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404

    # --- get_executors_for_task_handler ---

    @pytest.mark.asyncio
    async def test_get_executors_for_task_happy(self, mocks, patch_service):
        task_id = uuid.uuid4()
        fake_list = [
            {"task_id": str(task_id), "user_id": str(uuid.uuid4()), "estimate": 3},
            {"task_id": str(task_id), "user_id": str(uuid.uuid4()), "estimate": 5},
        ]
        patch_service.get_executors_for_task.return_value = fake_list
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        res = await get_executors_for_task_handler(
            task_id=task_id,
            data_manager=mocks["data_manager"],
        )
        assert isinstance(res, list)
        assert len(res) == 2

    @pytest.mark.asyncio
    async def test_get_executors_for_task_task_not_found(self, mocks, patch_service):
        task_id = uuid.uuid4()

        patch_service.get_executors_for_task.side_effect = TaskNotFound()
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await get_executors_for_task_handler(
                task_id=task_id,
                data_manager=mocks["data_manager"],
            )
        assert e.value.status_code == 404




    @pytest.mark.asyncio
    async def test_get_tasks_for_user_user_not_found(self, mocks, patch_service):
        user_id = uuid.uuid4()

        patch_service.get_tasks_for_user.side_effect = Exception("не найден")
        mod.TaskExecutorService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await get_tasks_for_user_handler(
                user_id=user_id,
                data_manager=mocks["data_manager"],
                page=1,
                page_size=10,
            )
        assert e.value.status_code == 404
