from abc import ABC, abstractmethod
from sqlalchemy.orm import DeclarativeBase, selectinload
from typing import Optional, Sequence, Tuple, TypeVar, Generic
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.src.dal.database.models import UserModel, TeamModel, ProjectModel, TaskExecutorModel, TaskModel, MeetingModel, EventModel, team_project_table


ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(ABC, Generic[ModelType]):
    """
    Абстрактный базовый репозиторий для всех моделей.

    Обеспечивает универсальные CRUD-операции и пагинацию.
    Является шаблоном для конкретных репозиториев.
    Использует принципы DRY, SOLID и DDD.

    Аргументы:
        session (AsyncSession): Асинхронная сессия SQLAlchemy.
        model (Type[ModelType]): Класс модели, с которой работает репозиторий.
    """

    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session = session
        self.model = model

    @abstractmethod
    async def get_by_id(self, obj_id: UUID) -> Optional[ModelType]:
        """
        Получает объект по ID.

        Аргументы:
            obj_id (UUID): Идентификатор объекта.

        Возвращает:
            Optional[ModelType]: Объект или None.
        """
        pass

    async def create(self, obj: ModelType) -> ModelType:
        """
        Сохраняет новый объект.

        Аргументы:
            obj (ModelType): Экземпляр объекта.

        Возвращает:
            ModelType: Сохранённый объект.
        """
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: ModelType) -> ModelType:
        """
        Обновляет объект.

        Аргументы:
            obj (ModelType): Обновлённый экземпляр.

        Возвращает:
            ModelType: Обновлённый объект.
        """
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelType) -> None:
        """
        Удаляет объект.

        Аргументы:
            obj (ModelType): Объект для удаления.
        """
        await self.session.delete(obj)

    async def get_all(self) -> Sequence[ModelType]:
        """
        Возвращает все объекты без пагинации.

        Возвращает:
            Sequence[ModelType]: Список всех объектов.
        """
        result = await self.session.execute(select(self.model))
        return result.scalars().all()

    async def get_all_paginated(
        self,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[Sequence[ModelType], int]:
        """
        Возвращает список объектов с пагинацией.

        Аргументы:
            page (int): Номер страницы (>=1).
            page_size (int): Размер страницы (>=1).

        Возвращает:
            Tuple[Sequence[ModelType], int]: Список объектов и общее количество.
        """
        offset = (page - 1) * page_size
        stmt = select(self.model)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar_one()

        stmt = stmt.limit(page_size).offset(offset)
        result = await self.session.execute(stmt)
        objects = result.scalars().all()

        return objects, total
    
    async def get_all_paginated_by_stmt(
        self,
        stmt,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[Sequence[ModelType], int]:
        """
        Возвращает объекты по кастомному запросу с пагинацией.

        Аргументы:
            stmt: SQL-запрос (select).
            page: Номер страницы.
            page_size: Размер страницы.

        Возвращает:
            (список объектов, общее количество)
        """
        offset = (page - 1) * page_size

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar_one()

        stmt = stmt.limit(page_size).offset(offset)
        result = await self.session.execute(stmt)
        objects = result.scalars().all()

        return objects, total


class UserRepository(BaseRepository[UserModel]):
    """
    Репозиторий для работы с пользователями.

    Наследует общий CRUD-функционал от BaseRepository.
    Реализует специфичные методы: get_by_email, get_by_role.

    Аргументы:
        session (AsyncSession): Асинхронная сессия для выполнения запросов.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, UserModel)

    async def get_by_id(self,  obj_id: UUID) -> Optional[UserModel]:  
        """
        Получает пользователя по ID.

        Аргументы:
            user_id (UUID): Идентификатор пользователя.

        Возвращает:
            Optional[UserModel]: Пользователь или None.
        """
        return await self.session.get(self.model, obj_id)

    async def get_by_email(self, email: str) -> Optional[UserModel]:
        """
        Получает пользователя по email.

        Аргументы:
            email (str): Email для поиска.

        Возвращает:
            Optional[UserModel]: Пользователь или None.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_by_role(self, role: str) -> Sequence[UserModel]:
        """
        Получает пользователя по role.

        Аргументы:
            role (str): role для поиска.

        Возвращает:
            Sequence[UserModel]: Список пользователей с указанной ролью.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.role == role)
        )
        return result.scalars().all()
    
    async def get_all_paginated(
        self, 
        page: int = 1, 
        page_size: int = 10,
        role: Optional[str] = None
    ) -> Tuple[Sequence[UserModel], int]:
        """
        Возвращает список пользователей с пагинацией и опциональной фильтрацией по роли.

        Аргументы:
            page (int): Номер страницы (>=1).
            page_size (int): Размер страницы (>=1).
            role (Optional[str]): Фильтр: пользователи с указанной ролью.

        Возвращает:
            Tuple[Sequence[UserModel], int]: Список пользователей и общее количество.
        """
        offset = (page - 1) * page_size
        stmt = select(self.model)

        if role:
            stmt = stmt.where(self.model.role == role)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar_one()

        stmt = stmt.limit(page_size).offset(offset)
        result = await self.session.execute(stmt)
        users = result.scalars().all()

        return users, total



class TeamRepository(BaseRepository):
    """
    Репозиторий для работы с TeamModel.

    Уникальная логика:
        - get_by_name: получить команду по названию.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, TeamModel) 

    async def get_by_name(self, name: str) -> TeamModel | None:
        stmt = select(self.model).where(self.model.name == name)
        result = await self.session.scalars(stmt)
        return result.first()


class ProjectRepository(BaseRepository):
    """
    Репозиторий для работы с ProjectModel.

    Уникальная логика:
        - get_by_name: получить проект по названию.
        - get_by_user_id: получить все проекты, в которых участвует пользователь.
        - get_teams_for_project: получить все команды проекта.
        - get_users_for_project: получить всех пользователей, связанных с проектом (через команды и исполнителей задач).
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProjectModel) 


    async def get_by_name(self, name: str) -> ProjectModel | None:
        stmt = select(self.model).where(self.model.name == name)
        result = await self.session.scalars(stmt)
        return result.first()

    async def get_by_user_id(self, user_id: UUID) -> Sequence[ProjectModel]:
        stmt = (
            select(self.model)
            .join(TeamModel)
            .join(UserModel, UserModel.team_id == TeamModel.id)
            .where(UserModel.id == user_id)
        )
        result = await self.session.scalars(stmt)
        return result.unique().all()

    async def get_teams_for_project(self, project_id: UUID) -> Sequence[TeamModel]:
        stmt = select(TeamModel).join(team_project_table).where(team_project_table.c.project_id == project_id)
        result = await self.session.scalars(stmt)
        return result.unique().all()

    async def get_users_for_project(self, project_id: UUID) -> list[UserModel]:
        # Пользователи: через команды, связанные с проектом
        stmt_teams = (
            select(UserModel)
            .join(TeamModel)
            .join(team_project_table)
            .where(team_project_table.c.project_id == project_id)
        )
        users_from_teams = await self.session.scalars(stmt_teams)

        # Пользователи: как исполнители задач проекта
        stmt_executors = (
            select(UserModel)
            .join(TaskExecutorModel)
            .join(TaskModel)
            .where(TaskModel.project_id == project_id)
        )
        users_from_tasks = await self.session.scalars(stmt_executors)

        # Объединяем и удаляем дубликаты
        return list({user.id: user for user in list(users_from_teams) + list(users_from_tasks)}.values())


class TaskRepository(BaseRepository):
    """
    Репозиторий для работы с TaskModel.

    Уникальная логика:
        - get_by_project_id: получить все задачи проекта.
        - get_by_user_id: получить все задачи, где пользователь — исполнитель.
        - get_sub_tasks: получить все подзадачи для родительской задачи.
        - get_parent_task: получить родительскую задачу для подзадачи.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, TaskModel) 


    async def get_by_project_id(self, project_id: UUID) -> Sequence[TaskModel]:
        stmt = select(self.model).where(self.model.project_id == project_id)
        result = await self.session.scalars(stmt)
        return result.unique().all()

    async def get_by_user_id(self, user_id: UUID) -> Sequence[TaskModel]:
        stmt = (
            select(self.model)
            .join(TaskExecutorModel)
            .where(TaskExecutorModel.user_id == user_id)
        )
        result = await self.session.scalars(stmt)
        return result.unique().all()

    async def get_sub_tasks(self, parent_id: UUID) -> Sequence[TaskModel]:
        stmt = select(self.model).where(self.model.parent_id == parent_id)
        result = await self.session.scalars(stmt)
        return result.unique().all()

    async def get_parent_task(self, task_id: UUID) -> TaskModel | None:
        stmt = select(self.model).where(self.model.id == task_id).options(selectinload(self.model.parent))
        result = await self.session.scalars(stmt)
        return result.first()
    
    async def get_tasks_by_team_and_priority(
        self,
        team_id: UUID,
        priority: Optional[str] = None,
    ) -> Sequence[TaskModel]:
        """
        Получает задачи команды с опциональной фильтрацией по приоритету.

        Аргументы:
            team_id (UUID): ID команды.
            priority (Optional[str]): Фильтр по приоритету (low, medium, high).

        Возвращает:
            Sequence[TaskModel]: Список задач.
        """
        stmt = select(self.model).where(self.model.team_id == team_id)
        if priority:
            stmt = stmt.where(self.model.priority == priority)
        result = await self.session.execute(stmt)
        return result.scalars().all()



class TaskExecutorRepository(BaseRepository):
    """
    Репозиторий для работы с TaskExecutorModel.

    Уникальная логика:
        - get_by_task_and_user: получить исполнителя задачи.
        - delete_by_task_and_user: удалить связку задача-исполнитель.
        - get_executors_for_task: получить всех исполнителей задачи.
        - get_tasks_for_user: получить все задачи пользователя.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, TaskExecutorModel) 


    async def get_by_task_and_user(self, task_id: UUID, user_id: UUID) -> TaskExecutorModel | None:
        stmt = select(self.model).where(
            self.model.task_id == task_id,
            self.model.user_id == user_id,
        )
        result = await self.session.scalars(stmt)
        return result.first()

    async def delete_by_task_and_user(self, task_id: UUID, user_id: UUID) -> None:
        stmt = delete(self.model).where(
            self.model.task_id == task_id,
            self.model.user_id == user_id,
        )
        await self.session.execute(stmt)

    async def get_executors_for_task(self, task_id: UUID) -> Sequence[UserModel]:
        stmt = (
            select(UserModel)
            .join(TaskExecutorModel)
            .where(TaskExecutorModel.task_id == task_id)
        )
        result = await self.session.scalars(stmt)
        return result.unique().all()

    async def get_tasks_for_user(self, user_id: UUID) -> Sequence[TaskModel]:
        stmt = (
            select(TaskModel)
            .join(TaskExecutorModel)
            .where(TaskExecutorModel.user_id == user_id)
        )
        result = await self.session.scalars(stmt)
        return result.unique().all()


class MeetingRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, model=MeetingModel) 


class EventRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, model=EventModel) 
