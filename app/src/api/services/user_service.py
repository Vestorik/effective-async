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

from passlib.context import CryptContext

from app.src.api.exceptions import UserNotFound
from app.src.api.services.base_services import BaseService
from app.src.api.shems import UserCreateSheme, UserOutSheme, UserUpdateSheme
from app.src.dal.database.repositories import UserRepository

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

from app.src.dal.database.models import UserModel

logger = getLogger(__name__)


class UserService(BaseService):
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
    
    async def create(
        self,
        repository: UserRepository,
        obj: UserCreateSheme,
    ) -> UserOutSheme:
        """
        Создаёт нового пользователя.

        Аргументы:
            repository: UserRepository.
            obj (UserCreateSheme): Входные данные пользователя.

        Возвращает:
            UserOutSheme: Созданный пользователь.

        Исключения:
            UserAlreadyExists: Если email уже занят.
        """


        # Проверка уникальности email
        existing_user = await repository.get_by_email(obj.email)
        if existing_user:
            from app.src.api.exceptions import UserAlreadyExists
            raise UserAlreadyExists()

        # Хэширование пароля и создание модели
        hashed_password = pwd_context.hash(obj.password)
        user = UserModel(
            username=obj.username,
            email=obj.email,
            hashed_password=hashed_password,
            role=obj.role,
            team_id=obj.team_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        await repository.create(user)
        return UserOutSheme.model_validate(user)

    async def get_user_by_id(
        self,
        repository: UserRepository,
        obj_id: UUID
    ) -> UserOutSheme:
        """
        Получает пользователя по ID.

        Аргументы:
            repository: Экземпляр UserRepository.
            obj_id (UUID): ID пользователя.

        Возвращает:
            UserOutSheme: Пользователь.

        Исключения:
            UserNotFound: Если пользователь не найден.
        """
        user = await repository.get_by_id(obj_id)
        if not user:
            raise UserNotFound()
        return UserOutSheme.model_validate(user)

    async def get_user_by_email(
        self,
        repository: UserRepository,
        email: str
    ) -> Optional[UserOutSheme]:
        """
        Получает пользователя по email.

        Аргументы:
            repository: Экземпляр UserRepository.
            email (str): Email.

        Возвращает:
            UserOutSheme | None: Пользователь или None.
        """
        user = await repository.get_by_email(email)
        return UserOutSheme.model_validate(user) if user else None

    async def get_all_users(
        self,
        repository: UserRepository,
        page: int = 1,
        page_size: int = 10,
        role: Optional[str] = None
    ) -> Tuple[List[UserOutSheme], int]:
        """
        Получает всех пользователей с пагинацией и опциональной фильтрацией по роли.

        Аргументы:
            repository: Экземпляр UserRepository.
            page (int): Номер страницы.
            page_size (int): Размер страницы.
            role (str | None): Фильтр по роли.

        Возвращает:
            (list[UserOutSheme], int): Список пользователей и общее количество.
        """
        users, total = await repository.get_all_paginated(page=page, page_size=page_size, role=role)
        return [UserOutSheme.model_validate(u) for u in users], total

    async def update_user(
        self,
        repository: UserRepository,
        obj_id: UUID,
        user_data: UserUpdateSheme,
    ) -> UserOutSheme:
        """
        Обновляет данные пользователя.

        Аргументы:
            repository: Экземпляр UserRepository.
            obj_id (UUID): ID пользователя.
            user_data (UserUpdateSheme): Новые данные.

        Возвращает:
            UserOutSheme: Обновлённый пользователь.

        Исключения:
            UserNotFound: Если пользователь не найден.
        """
        user = await repository.get_by_id(obj_id)
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

        await repository.update(user)
        return UserOutSheme.model_validate(user)

    async def delete_user(
        self,
        repository: UserRepository,
        obj_id: UUID
    ) -> None:
        """
        Удаляет пользователя.

        Аргументы:
            repository: Экземпляр UserRepository.
            obj_id (UUID): ID пользователя.

        Исключения:
            UserNotFound: Если пользователь не найден.
        """
        user = await repository.get_by_id(obj_id)
        if not user:
            raise UserNotFound()
        await repository.delete(user)
        
        
        

# # --- EXISTING CODE: UserService переписан под наследование ---

# class UserService(BaseService[UserModel, UserRepository]):  # <-- НАСЛЕДУЕТ
#     """
#     Сервис управления пользователями.

#     Наследует базовую CRUD-логику от `BaseService`.
#     Реализует специфичные методы: `get_user_by_email`.

#     Аргументы:
#         None (все зависимости внедряются через методы).

#     Методы:
#         get_user_by_id: Получает пользователя по ID.
#         get_user_by_email: Получает пользователя по email.
#         get_all_users: Получает всех пользователей с пагинацией и фильтрацией.
#         update_user: Обновляет данные пользователя.
#         delete_user: Удаляет пользователя.
#     """

#     # --- Переопределяем методы с кастомной логикой или обёртками ---

#     async def get_user_by_email(
#         self,
#         user_repo: UserRepository,
#         email: str
#     ) -> Optional[UserOutSheme]:
#         """
#         Получает пользователя по email.

#         Аргументы:
#             user_repo: Экземпляр UserRepository.
#             email (str): Email.

#         Возвращает:
#             UserOutSheme | None: Пользователь или None.
#         """
#         user = await user_repo.get_by_email(email)
#         return UserOutSheme.model_validate(user) if user else None

#     async def get_all_users(
#         self,
#         user_repo: UserRepository,
#         page: int = 1,
#         page_size: int = 10,
#         role: Optional[str] = None
#     ) -> Tuple[List[UserOutSheme], int]:
#         """
#         Получает всех пользователей с пагинацией и фильтрацией по роли.

#         Аргументы:
#             user_repo: Экземпляр UserRepository.
#             page (int): Номер страницы.
#             page_size (int): Размер страницы.
#             role (str | None): Фильтр по роли.

#         Возвращает:
#             (list[UserOutSheme], int): Список пользователей и общее количество.
#         """
#         users, total = await user_repo.get_all_paginated(page=page, page_size=page_size, role=role)
#         return [UserOutSheme.model_validate(u) for u in users], total

#     async def update_user(
#         self,
#         user_repo: UserRepository,
#         user_id: UUID,
#         user_data: UserUpdateSheme,
#     ) -> UserOutSheme:
#         """
#         Обновляет данные пользователя.

#         Аргументы:
#             user_repo: Экземпляр UserRepository.
#             user_id (UUID): ID пользователя.
#             user_data (UserUpdateSheme): Новые данные.

#         Возвращает:
#             UserOutSheme: Обновлённый пользователь.

#         Исключения:
#             UserNotFound: Если пользователь не найден.
#         """
#         user = await user_repo.get_by_id(user_id)
#         if not user:
#             raise UserNotFound()

#         if user_data.username is not None:
#             user.username = user_data.username
#         if user_data.email is not None:
#             user.email = user_data.email
#         if user_data.role is not None:
#             user.role = user_data.role
#         if user_data.team_id is not None:
#             user.team_id = user_data.team_id

#         user.updated_at = datetime.now(timezone.utc)

#         await user_repo.update(user)
#         return UserOutSheme.model_validate(user)

#     # Стандартные методы (create/delete/get_by_id/get_all/get_all_paginated) теперь наследуются от BaseService.

#     # Пример (если понадобится явная реализация):
#     # async def create_user(self, ...) -> UserOutSheme:
#     #     ...