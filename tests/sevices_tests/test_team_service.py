"""Тесты для TeamService: create_team, get_team_by_id, get_all_teams, join_team.

Покрытые кейсы:
- create_team: success, team already exists, manager not found
- get_team_by_id: found, not found
- get_all_teams: success
- join_team: success, team not found, user not found, user already in team
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID
from datetime import datetime

from app.src.api.services.team_service import TeamService
from app.src.api.exceptions import TeamAlreadyExists, TeamNotFound
from app.src.dal.database.repositories import TeamRepository, UserRepository
from app.src.dal.database.models import TeamModel, UserModel
from app.src.api.shems import TeamSchema, TeamSchemaOut


def create_mock_team(
    team_id: UUID | None = None,
    name: str = "Test Team",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> TeamModel:
    """Создает мок TeamModel для тестов."""
    team = MagicMock(spec=TeamModel)
    team.id = team_id or uuid4()
    team.name = name
    team.created_at = created_at or datetime.now()
    team.updated_at = updated_at or datetime.now()
    team._sa_instance_state = MagicMock()
    return team


def create_mock_user(
    user_id: UUID | None = None,
    username: str = "testuser",
    email: str = "test@example.com",
    role: str = "user",
    team_id: UUID | None = None,
) -> UserModel:
    """Создает мок UserModel для тестов."""
    user = MagicMock(spec=UserModel)
    user.id = user_id or uuid4()
    user.username = username
    user.email = email
    user.role = role
    user.team_id = team_id
    user._sa_instance_state = MagicMock()
    return user


@pytest.fixture
def team_service() -> TeamService:
    """Экземпляр TeamService."""
    return TeamService()


@pytest.fixture
def mock_team_repo() -> AsyncMock:
    """Моковый TeamRepository."""
    return AsyncMock(spec=TeamRepository)


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Моковый UserRepository."""
    return AsyncMock(spec=UserRepository)


class TestTeamServiceCreateTeam:
    """Тесты для метода create_team."""

    @pytest.mark.asyncio
    async def test_create_team_success(self, team_service, mock_team_repo, mock_user_repo):
        """Успешное создание команды."""
        team_id = uuid4()
        manager_id = uuid4()
        team_name = "New Team"
        
        mock_team = create_mock_team(team_id, team_name)
        mock_manager = create_mock_user(manager_id)
        
        mock_team_repo.get_by_name = AsyncMock(return_value=None)
        mock_team_repo.create = AsyncMock(return_value=mock_team)
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_manager)
        mock_user_repo.update = AsyncMock()

        result = await team_service.create_team(
            team_repo=mock_team_repo,
            user_repo=mock_user_repo,
            name=team_name,
            manager_id=manager_id,
        )

        assert result is not None
        assert isinstance(result, TeamSchema)
        assert result.name == team_name
        mock_team_repo.get_by_name.assert_called_once_with(team_name)
        mock_team_repo.create.assert_called_once()
        mock_user_repo.get_by_id.assert_called_once_with(manager_id)
        mock_user_repo.update.assert_called_once()


    @pytest.mark.asyncio
    async def test_create_team_already_exists(self, team_service, mock_team_repo, mock_user_repo):
        """Создание команды с существующим названием."""
        team_name = "Existing Team"
        existing_team = create_mock_team(name=team_name)
        mock_team_repo.get_by_name = AsyncMock(return_value=existing_team)

        with pytest.raises(TeamAlreadyExists):
            await team_service.create_team(
                team_repo=mock_team_repo,
                user_repo=mock_user_repo,
                name=team_name,
                manager_id=uuid4(),
            )

        mock_team_repo.create.assert_not_called()
        mock_user_repo.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_team_manager_not_found(self, team_service, mock_team_repo, mock_user_repo):
        """Создание команды с несуществующим менеджером."""
        team_name = "New Team"
        manager_id = uuid4()
        
        mock_team_repo.get_by_name = AsyncMock(return_value=None)
        mock_team_repo.create = AsyncMock(return_value=create_mock_team())
        mock_user_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="Менеджер не найден"):
            await team_service.create_team(
                team_repo=mock_team_repo,
                user_repo=mock_user_repo,
                name=team_name,
                manager_id=manager_id,
            )


class TestTeamServiceGetTeamById:
    """Тесты для метода get_team_by_id."""

    @pytest.mark.asyncio
    async def test_get_team_by_id_found(self, team_service, mock_team_repo):
        """Получение команды по существующему ID."""
        team_id = uuid4()
        mock_team = create_mock_team(team_id)
        mock_team_repo.get_by_id = AsyncMock(return_value=mock_team)

        result = await team_service.get_team_by_id(mock_team_repo, team_id)

        assert result is not None
        assert isinstance(result, TeamSchema)
        mock_team_repo.get_by_id.assert_called_once_with(team_id)

    @pytest.mark.asyncio
    async def test_get_team_by_id_not_found(self, team_service, mock_team_repo):
        """Получение команды с несуществующим ID."""
        team_id = uuid4()
        mock_team_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TeamNotFound):
            await team_service.get_team_by_id(mock_team_repo, team_id)


class TestTeamServiceGetAllTeams:
    """Тесты для метода get_all_teams."""

    @pytest.mark.asyncio
    async def test_get_all_teams_success(self, team_service, mock_team_repo):
        """Получение списка всех команд."""
        teams = [
            create_mock_team(name="Team 1"),
            create_mock_team(name="Team 2"),
        ]
        mock_team_repo.get_all = AsyncMock(return_value=teams)

        result = await team_service.get_all_teams(mock_team_repo)

        assert len(result) == 2
        assert all(isinstance(t, TeamSchemaOut) for t in result)
        assert result[0].name == "Team 1"
        assert result[1].name == "Team 2"
        mock_team_repo.get_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_teams_empty(self, team_service, mock_team_repo):
        """Получение пустого списка команд."""
        mock_team_repo.get_all = AsyncMock(return_value=[])

        result = await team_service.get_all_teams(mock_team_repo)

        assert result == []


class TestTeamServiceJoinTeam:
    """Тесты для метода join_team."""

    @pytest.mark.asyncio
    async def test_join_team_success(self, team_service, mock_team_repo, mock_user_repo):
        """Успешное вступление в команду."""
        team_id = uuid4()
        user_id = uuid4()
        
        mock_team = create_mock_team(team_id)
        mock_user = create_mock_user(user_id, team_id=None)
        
        mock_team_repo.get_by_id = AsyncMock(return_value=mock_team)
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
        mock_user_repo.update = AsyncMock()

        result = await team_service.join_team(
            team_repo=mock_team_repo,
            user_repo=mock_user_repo,
            user_id=user_id,
            team_id=team_id,
        )

        assert isinstance(result, TeamSchema)
        assert mock_user.team_id == team_id
        mock_user_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_join_team_not_found(self, team_service, mock_team_repo, mock_user_repo):
        """Вступление в несуществующую команду."""
        team_id = uuid4()
        user_id = uuid4()
        
        mock_team_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TeamNotFound):
            await team_service.join_team(
                team_repo=mock_team_repo,
                user_repo=mock_user_repo,
                user_id=user_id,
                team_id=team_id,
            )

    @pytest.mark.asyncio
    async def test_join_team_user_not_found(self, team_service, mock_team_repo, mock_user_repo):
        """Вступление несуществующего пользователя."""
        team_id = uuid4()
        user_id = uuid4()
        
        mock_team_repo.get_by_id = AsyncMock(return_value=create_mock_team(team_id))
        mock_user_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Пользователь не найден"):
            await team_service.join_team(
                team_repo=mock_team_repo,
                user_repo=mock_user_repo,
                user_id=user_id,
                team_id=team_id,
            )

    @pytest.mark.asyncio
    async def test_join_team_user_already_in_team(self, team_service, mock_team_repo, mock_user_repo):
        """Пользователь уже состоит в команде."""
        team_id = uuid4()
        user_id = uuid4()
        existing_team_id = uuid4()
        
        mock_team = create_mock_team(team_id)
        mock_user = create_mock_user(user_id, team_id=existing_team_id)
        
        mock_team_repo.get_by_id = AsyncMock(return_value=mock_team)
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        with pytest.raises(ValueError, match="Пользователь уже состоит в команде"):
            await team_service.join_team(
                team_repo=mock_team_repo,
                user_repo=mock_user_repo,
                user_id=user_id,
                team_id=team_id,
            )
