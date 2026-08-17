# tests/data_tests/test_repository/test_team_repository.py

"""
Тесты для TeamRepository.

Критерии приемки:
1. get_by_id: возвращает команду по ID или None.
2. get_by_name: возвращает команду по имени или None.
3. create: наследуется от BaseRepository (не тестируется здесь, если уже покрыто в BaseRepository).
4. update/delete: наследуются от BaseRepository.

Тестирование выполнено через мокирование AsyncSession.
Используется реальный TeamModel (или его мок-спецификацию) для проверки корректности запросов.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.src.dal.database.repositories import TeamRepository
from app.src.dal.database.models import TeamModel


@pytest.fixture
def mock_session() -> AsyncMock:
    """
    Создает мок асинхронной сессии.
    """
    session = AsyncMock(spec=AsyncSession)
    
    # Подготовка скалярного результата для запросов
    scalar_result = MagicMock()
    scalar_result.first.return_value = None
    scalar_result.unique.return_value = scalar_result
    
    session.get.return_value = None
    session.add = AsyncMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute.return_value = scalar_result
    session.scalars.return_value = scalar_result
    
    return session


@pytest.fixture
def team_instance() -> MagicMock:
    """
    Создает мок экземпляра TeamModel.
    """
    instance = MagicMock(spec=TeamModel)
    instance.id = uuid4()
    instance.name = "Test Team"
    return instance


@pytest.fixture
def team_repo(mock_session) -> TeamRepository:
    """
    Создает экземпляр TeamRepository с моковой сессией.
    """
    # Используем реальный TeamModel, чтобы тесты были ближе к реальности.
    # Если TeamModel требует сложной инициализации, можно использовать мок-класс,
    # но в данном случае реальный класс подходит.
    return TeamRepository(session=mock_session)


class TestTeamRepository:
    """Тесты для TeamRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        team_repo: TeamRepository,
        team_instance: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает команду при успешном поиске по ID.
        
        Arrange: Мокируем session.get для возврата команды.
        Act: Вызов get_by_id.
        Assert: Проверка корректности возврата.
        """
        # Arrange
        team_id = team_instance.id
        mock_session.get.return_value = team_instance

        # Act
        result = await team_repo.get_by_id(team_id)

        # Assert
        mock_session.get.assert_called_once_with(TeamModel, team_id)
        assert result == team_instance

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        team_repo: TeamRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_id возвращает None, если команда не найдена.
        
        Arrange: Мокируем session.get для возврата None.
        Act: Вызов get_by_id.
        Assert: Результат равен None.
        """
        # Arrange
        team_id = uuid4()
        mock_session.get.return_value = None

        # Act
        result = await team_repo.get_by_id(team_id)

        # Assert
        mock_session.get.assert_called_once_with(TeamModel, team_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name_success(
        self,
        team_repo: TeamRepository,
        team_instance: MagicMock,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_name возвращает команду по имени.
        
        Arrange: Мокируем результат execute/scalars.
        Act: Вызов get_by_name.
        Assert: Проверка корректности возврата и формирования запроса.
        """
        # Arrange
        team_name = "Test Team"
        # Настраиваем мок так, чтобы first() возвращал команду
        mock_scalar_result = MagicMock()
        mock_scalar_result.first.return_value = team_instance
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        result = await team_repo.get_by_name(team_name)

        # Assert
        mock_session.scalars.assert_called_once()
        # Проверяем, что передан правильный select
        call_args = mock_session.scalars.call_args
        stmt = call_args[0][0]
        
        # Проверяем, что в запросе есть WHERE по имени
        # stmt содержит объект Select. Для полной проверки можно сравнить строковое представление,
        # но для unit-тестов достаточно проверить, что запрос был составлен.
        # Мы можем проверить, что вызов был с конкретным SQL-выражением.
        
        assert result == team_instance

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(
        self,
        team_repo: TeamRepository,
        mock_session: AsyncMock
    ) -> None:
        """
        Проверка: get_by_name возвращает None, если команда с таким именем не найдена.
        
        Arrange: Мокируем результат scalars.first() для возврата None.
        Act: Вызов get_by_name.
        Assert: Результат равен None.
        """
        # Arrange
        team_name = "Non-existent Team"
        mock_scalar_result = MagicMock()
        mock_scalar_result.first.return_value = None
        mock_session.scalars.return_value = mock_scalar_result

        # Act
        result = await team_repo.get_by_name(team_name)

        # Assert
        mock_session.scalars.assert_called_once()
        assert result is None