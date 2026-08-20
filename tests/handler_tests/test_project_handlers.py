import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.exceptions import HTTPException

from app.src.api.handlers.project_handlers import (
    get_project_by_id,
    create_project,
    get_projects_for_team,
    update_project,
    delete_project,
    get_projects_for_user,
)
from app.src.api.shems import ProjectCreate, ProjectUpdate
from app.src.api.exceptions import ProjectNotFound
import app.src.api.handlers.project_handlers as mod


class TestProjectHandlers:
    @pytest.fixture
    def mocks(self):
        """Базовые моки для DataManager, UOW и кэшированного UOW."""
        data_manager = MagicMock()
        uow = MagicMock()
        data_manager.return_value.__aenter__.return_value = uow
        uow.projects = MagicMock()
        uow.teams = MagicMock()

        # Кэшированный UOW (нужен для get_project_by_id и других get)
        cuow = MagicMock()
        data_manager.cache.return_value.__aenter__.return_value = cuow

        return {
            "data_manager": data_manager,
            "uow": uow,
            "cuow": cuow,
        }

    @pytest.fixture
    def patch_service(self):
        """Подменяет ProjectService в модуле и гарантирует возврат старого класса после теста."""
        old_ProjectService = mod.ProjectService
        mock_service = AsyncMock()

        def teardown():
            mod.ProjectService = old_ProjectService

        yield mock_service
        teardown()

    # --- get_project_by_id ---


    @pytest.mark.asyncio
    async def test_get_project_by_id_not_found(self, mocks):
        pid = uuid.uuid4()
        mocks["cuow"].projects.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as e:
            await get_project_by_id(project_id=pid, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404



    @pytest.mark.asyncio
    async def test_create_project_already_exists(self, mocks, patch_service):
        payload = ProjectCreate(name="dup", description="desc", team_ids=[uuid.uuid4()])
        patch_service.create_project.side_effect = Exception("проект с таким названием уже существует")
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await create_project(project_data=payload, data_manager=mocks["data_manager"])
        assert e.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_project_team_not_found(self, mocks, patch_service):
        payload = ProjectCreate(name="bad-team", description="desc", team_ids=[uuid.uuid4()])
        patch_service.create_project.side_effect = Exception("команда не найдена")
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await create_project(project_data=payload, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404

    # --- get_projects_for_team ---

    @pytest.mark.asyncio
    async def test_get_projects_for_team_happy(self, mocks, patch_service):
        tid = uuid.uuid4()
        fake_list = [{"id": str(uuid.uuid4()), "name": "p1"}, {"id": str(uuid.uuid4()), "name": "p2"}]
        patch_service.get_projects_for_team.return_value = fake_list
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        res = await get_projects_for_team(team_id=tid, data_manager=mocks["data_manager"])
        assert isinstance(res, list)
        assert len(res) == 2

    @pytest.mark.asyncio
    async def test_get_projects_for_team_not_found(self, mocks, patch_service):
        tid = uuid.uuid4()
        patch_service.get_projects_for_team.side_effect = ProjectNotFound()
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await get_projects_for_team(team_id=tid, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404


    @pytest.mark.asyncio
    async def test_update_project_not_found(self, mocks, patch_service):
        pid = uuid.uuid4()
        payload = ProjectUpdate(name="upd", description="d", team_ids=[uuid.uuid4()])
        patch_service.update_project.side_effect = ProjectNotFound()
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await update_project(
                project_id=pid, project_update=payload, data_manager=mocks["data_manager"]
            )
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_project_team_missing(self, mocks, patch_service):
        pid = uuid.uuid4()
        payload = ProjectUpdate(name="bad", description="d", team_ids=[uuid.uuid4()])
        # Ловим общий Exception с фразой «не найдена», как в твоём коде
        patch_service.update_project.side_effect = Exception("одна из команд не найдена")
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await update_project(
                project_id=pid, project_update=payload, data_manager=mocks["data_manager"]
            )
        # В твоём коде это превращается в 400, а не 404
        assert e.value.status_code == 400

    # --- delete_project ---

    @pytest.mark.asyncio
    async def test_delete_project_success(self, mocks, patch_service):
        pid = uuid.uuid4()
        patch_service.delete_project.return_value = None
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        res = await delete_project(project_id=pid, data_manager=mocks["data_manager"])
        assert res is None  # FastAPI сам сделает 204

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, mocks, patch_service):
        pid = uuid.uuid4()
        patch_service.delete_project.side_effect = ProjectNotFound()
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await delete_project(project_id=pid, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404

    # --- get_projects_for_user ---

    @pytest.mark.asyncio
    async def test_get_projects_for_user_happy(self, mocks, patch_service):
        uid = uuid.uuid4()
        fake_list = [{"id": str(uuid.uuid4()), "name": "u1"}]
        patch_service.get_projects_for_user.return_value = fake_list
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        res = await get_projects_for_user(user_id=uid, data_manager=mocks["data_manager"])
        assert isinstance(res, list)
        assert len(res) == 1

    @pytest.mark.asyncio
    async def test_get_projects_for_user_not_found(self, mocks, patch_service):
        uid = uuid.uuid4()
        patch_service.get_projects_for_user.side_effect = ProjectNotFound()
        mod.ProjectService = lambda: patch_service  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        with pytest.raises(HTTPException) as e:
            await get_projects_for_user(user_id=uid, data_manager=mocks["data_manager"])
        assert e.value.status_code == 404
