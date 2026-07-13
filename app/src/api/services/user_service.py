"""
Сервис управления пользователями.

Методы:
    get_user_by_id: Получает пользователя по ID.
    get_user_by_email: Получает пользователя по email.
    get_all_users: Получает всех пользователей с пагинацией и фильтрацией.
    update_user: Обновляет данные пользователя (только базовое обновление, без смены роли/команды).
    delete_user: Удаляет пользователя.

Ограничения:
    - Валидация прав вынесена в handlers.py (через `Depends` или встроенные декораторы).
"""
from datetime import datetime, timezone

from logging import getLogger
from typing import List, Optional, Tuple
from uuid import UUID

from app.src.api.exceptions import UserNotFound
from app.src.api.shems import UserOutSheme, UserUpdateSheme
from app.src.dal.database.repositories import UserRepository

logger = getLogger(__name__)


class UserService:
    """
    Сервис управления пользователями.

    Взаимодействует с репозиториями через конкретные экземпляры (`UserRepository`).
    Это позволяет использовать сервис как с `UnitOfWork`, так и с `session_transaction`.

    Аргументы:
        None (все зависимости внедряются через методы).

    Методы:
        get_user_by_id: Получает пользователя по ID.
        get_user_by_email: Получает пользователя по email.
        get_all_users: Получает всех пользователей с пагинацией.
        update_user: Обновляет данные пользователя.
        delete_user: Удаляет пользователя.
    """

    async def get_user_by_id(
        self,
        user_repo: UserRepository,
        user_id: UUID
    ) -> UserOutSheme:
        """
        Получает пользователя по ID.

        Аргументы:
            user_repo: Экземпляр UserRepository.
            user_id (UUID): ID пользователя.

        Возвращает:
            UserOutSheme: Пользователь.

        Исключения:
            UserNotFound: Если пользователь не найден.
        """
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound()
        return UserOutSheme.model_validate(user)

    async def get_user_by_email(
        self,
        user_repo: UserRepository,
        email: str
    ) -> Optional[UserOutSheme]:
        """
        Получает пользователя по email.

        Аргументы:
            user_repo: Экземпляр UserRepository.
            email (str): Email.

        Возвращает:
            UserOutSheme | None: Пользователь или None.
        """
        user = await user_repo.get_by_email(email)
        return UserOutSheme.model_validate(user) if user else None

    async def get_all_users(
        self,
        user_repo: UserRepository,
        page: int = 1,
        page_size: int = 10,
        role: Optional[str] = None
    ) -> Tuple[List[UserOutSheme], int]:
        """
        Получает всех пользователей с пагинацией и опциональной фильтрацией по роли.

        Аргументы:
            user_repo: Экземпляр UserRepository.
            page (int): Номер страницы.
            page_size (int): Размер страницы.
            role (str | None): Фильтр по роли.

        Возвращает:
            (list[UserOutSheme], int): Список пользователей и общее количество.
        """
        users, total = await user_repo.get_all_paginated(page=page, page_size=page_size, role=role)
        return [UserOutSheme.model_validate(u) for u in users], total

    async def update_user(
        self,
        user_repo: UserRepository,
        user_id: UUID,
        user_data: UserUpdateSheme,
    ) -> UserOutSheme:
        """
        Обновляет данные пользователя.

        Аргументы:
            user_repo: Экземпляр UserRepository.
            user_id (UUID): ID пользователя.
            user_data (UserUpdateSheme): Новые данные.

        Возвращает:
            UserOutSheme: Обновлённый пользователь.

        Исключения:
            UserNotFound: Если пользователь не найден.
        """
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound()

        if user_data.username is not None:
            user.username = user_data.username
        if user_data.email is not None:
            user.email = user_data.email
        if user_data.role is not None:
            user.role = user_data.role
        if user_data.team_id is not None:
            user.team_id = user_data.team_id
            
        user.updated_at = datetime.now(timezone.utc)

        await user_repo.update(user)
        return UserOutSheme.model_validate(user)

    async def delete_user(
        self,
        user_repo: UserRepository,
        user_id: UUID
    ) -> None:
        """
        Удаляет пользователя.

        Аргументы:
            user_repo: Экземпляр UserRepository.
            user_id (UUID): ID пользователя.

        Исключения:
            UserNotFound: Если пользователь не найден.
        """
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound()
        await user_repo.delete(user)