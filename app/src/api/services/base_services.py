from abc import ABC
from typing import TypeVar, Generic, Sequence, Tuple, Optional
from uuid import UUID
from app.src.dal.database.repositories import BaseRepository, ModelType



RepositoryType = TypeVar("RepositoryType", bound=BaseRepository[ModelType])  # ty:ignore[invalid-type-arguments]



class BaseService(ABC, Generic[ModelType, RepositoryType]):
    """
    Абстрактный базовый сервис для всех сущностей.

    Обеспечивает универсальные CRUD-методы и пагинацию, проксируя вызовы к репозиторию.
    Является шаблоном для конкретных сервисов (UserService, TeamService и др.).

    Использует принципы DRY, SOLID, Dependency Injection и DDD.

    Аргументы:
        None (все зависимости внедряются через методы — через `Depends` или вручную).

    Методы:
        get_by_id: Получает объект по ID.
        get_all: Получает все объекты.
        get_all_paginated: Получает объекты с пагинацией.
        create: Создаёт новый объект.
        update: Обновляет объект.
        delete: Удаляет объект.
    """

    async def get_by_id(
        self, repository: RepositoryType, obj_id: UUID
    ) -> Optional[ModelType]:
        """Получает объект по ID через репозиторий."""
        return await repository.get_by_id(obj_id)

    async def get_all(self, repository: RepositoryType) -> Sequence[ModelType]:
        """Получает все объекты через репозиторий."""
        return await repository.get_all()

    async def get_all_paginated(
        self, repository: RepositoryType, page: int = 1, page_size: int = 10
    ) -> Tuple[Sequence[ModelType], int]:
        """Получает объекты с пагинацией через репозиторий."""
        return await repository.get_all_paginated(page=page, page_size=page_size)

    async def create(self, repository: RepositoryType, obj: ModelType) -> ModelType:
        """Создаёт новый объект через репозиторий."""
        return await repository.create(obj)

    async def update(self, repository: RepositoryType, obj: ModelType) -> ModelType:
        """Обновляет объект через репозиторий."""
        return await repository.update(obj)

    async def delete(self, repository: RepositoryType, obj: ModelType) -> None:
        """Удаляет объект через репозиторий."""
        await repository.delete(obj)
