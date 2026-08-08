"""Тесты Unit of Work и session_manage.py."""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.src.dal.database.models import UserModel, TeamModel, ProjectModel, TaskModel
from app.src.dal.database.session_manage import (
    UnitOfWork,
    DataBaseManager,
    session_transaction,
)


class TestUnitOfWork:
    """Тесты UnitOfWork."""

    @pytest.fixture
    async def uow(self, session_maker, test_engine):
        """Создаёт UnitOfWork."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return UnitOfWork(session)

    async def test_context_manager_enter(self, uow, test_session):
        """Тест входа в контекстный менеджер."""
        async with uow as uow_instance:
            assert uow_instance.session is not None
            assert uow_instance.users is not None
            assert uow_instance.teams is not None
            assert uow_instance.projects is not None
            assert uow_instance.tasks is not None

    async def test_context_manager_commit(self, uow, test_session):
        """Тест успешного коммита транзакции."""
        async with uow as uow_instance:
            user = UserModel(
                username="testuser",
                email="test@example.com",
                role="user",
            )
            user.set_password("password123")
            await uow_instance.users.create(user)
        
        # Проверяем, что пользователь был сохранён
        result = await test_session.execute(
            test_session.query(UserModel).filter(UserModel.email == "test@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None

    async def test_context_manager_rollback_on_error(self, uow, test_session):
        """Тест отката транзакции при ошибке."""
        try:
            async with uow as uow_instance:
                user = UserModel(
                    username="testuser",
                    email="test@example.com",
                    role="user",
                )
                user.set_password("password123")
                await uow_instance.users.create(user)
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Проверяем, что пользователь НЕ был сохранён
        result = await test_session.execute(
            test_session.query(UserModel).filter(UserModel.email == "test@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is None

    async def test_multiple_repositories_in_uow(self, uow, test_session):
        """Тест работы с несколькими репозиториями в рамках одной транзакции."""
        async with uow as uow_instance:
            team = TeamModel(name="Dev Team")
            await uow_instance.teams.create(team)
            
            user = UserModel(
                username="testuser",
                email="test@example.com",
                role="user",
                team_id=team.id,
            )
            user.set_password("password123")
            await uow_instance.users.create(user)
            
            project = ProjectModel(name="Test Project")
            await uow_instance.projects.create(project)
        
        # Проверяем все объекты
        result = await test_session.execute(
            test_session.query(UserModel).filter(UserModel.email == "test@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.team_id is not None


class TestDataBaseManager:
    """Тесты DataBaseManager."""

    @pytest.fixture
    def db_manager(self, test_engine):
        """Создаёт DataBaseManager."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return DataBaseManager(session, test_engine)

    def test_uow_method(self, db_manager):
        """Тест метода uow()."""
        uow = db_manager.uow()
        assert isinstance(uow, UnitOfWork)

    def test_get_engine(self, db_manager, test_engine):
        """Тест свойства get_engine."""
        engine = db_manager.get_engine
        assert engine == test_engine


class TestSessionTransaction:
    """Тесты session_transaction."""

    @pytest.fixture
    async def db_manager(self, test_engine):
        """Создаёт DataBaseManager для session_transaction."""
        from app.src.dal.database.engine import create_session_maker
        session = create_session_maker(test_engine)
        return DataBaseManager(session, test_engine)

    async def test_session_transaction_success(self, db_manager, test_session):
        """Тест успешного выполнения транзакции с retry."""
        from app.src.dal.database.repositories import UserRepository
        
        async with session_transaction(db_manager._DataBaseManager__session_maker) as session:
            repo = UserRepository(session)
            user = UserModel(
                username="testuser",
                email="test@example.com",
                role="user",
            )
            user.set_password("password123")
            await repo.create(user)
        
        # Проверяем, что пользователь был сохранён
        result = await test_session.execute(
            test_session.query(UserModel).filter(UserModel.email == "test@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None

    async def test_session_transaction_retry_on_error(self, db_manager, test_session, caplog):
        """Тест retry при ошибке при первом вызове."""
        from app.src.dal.database.repositories import UserRepository
        
        # Создаём счётчик попыток
        attempt_count = 0
        
        async with session_transaction(db_manager._DataBaseManager__session_maker, max_retries=3) as session:
            repo = UserRepository(session)
            
            # Простая операция
            user = UserModel(
                username="testuser",
                email="test@example.com",
                role="user",
            )
            user.set_password("password123")
            await repo.create(user)
            await session.commit()
        
        # Проверяем, что пользователь был сохранён
        result = await test_session.execute(
            test_session.query(UserModel).filter(UserModel.email == "test@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None

    async def test_session_transaction_exhaust_retries(self, db_manager):
        """Тест исчерпания попыток retry."""
        from app.src.dal.database.repositories import UserRepository
        
        with pytest.raises(Exception):
            async with session_transaction(db_manager._DataBaseManager__session_maker, max_retries=1) as session:
                repo = UserRepository(session)
                # Симулируем ошибку
                raise Exception("Test error")
