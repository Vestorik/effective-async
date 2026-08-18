from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.src.api.utils.api_utils import DataManager
from app.src.api.exceptions import UserNotFound
from app.src.api.services.user_service import UserService
from app.src.api.shems import UserCreateSheme, UserOutSheme, UserUpdateSheme

user_router = APIRouter(prefix="/users")


# === Пользователи ===
async def create_user_handler(
    user_data: UserCreateSheme,
    data_manager: DataManager,
) -> UserOutSheme:
    """
    Создание пользователя через UserService.

    Аргументы:
        user_data (UserCreateSheme): Данные пользователя.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        UserOutSheme: Созданный пользователь.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Валидация уникальности email и хэширование пароля выполняются в сервисе.

    Возможные исключения:
        HTTPException: 400 или 409, если пользователь с таким email уже существует.
    """
    async with data_manager() as uow:
        user_service = UserService()
        try:
            user = await user_service.create(
                repository=uow.users,
                obj=user_data,
            )
            return UserOutSheme.model_validate(user)
        except Exception as ex:
            # Перехват специфичных ошибок сервиса и преобразование в HTTP
            detail = str(ex)
            if "email" in detail.lower() or "exists" in detail.lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Пользователь с таким email уже существует",
                )
            raise


async def get_user_handler(
    user_id: UUID,
    data_manager: DataManager,
) -> UserOutSheme:
    """
    Получение пользователя по ID через кэшированный Unit of Work.

    Аргументы:
        user_id (UUID): ID пользователя.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        UserOutSheme: Данные пользователя.

    Дополнительная информация:
        - Кэширование TTL: 10 минут.
        - Используется `uow.users.get_by_id`.

    Возможные исключения:
        HTTPException: 404, если пользователь не найден.
    """
    async with data_manager.cache(timedelta(minutes=10)) as cuow:
        user = await cuow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )
        return UserOutSheme.model_validate(user)


async def update_user_handler(
    user_id: UUID,
    user_data: UserUpdateSheme,
    data_manager: DataManager,
) -> UserOutSheme:
    """
    Обновление пользователя через UserService.

    Аргументы:
        user_id (UUID): ID пользователя.
        user_data (UserUpdateSheme): Обновляемые данные.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        UserOutSheme: Обновлённый пользователь.

    Дополнительная информация:
        - Write-операция — не кэшируется.
        - Обновляются только непустые поля.

    Возможные исключения:
        HTTPException: 404, если пользователь не найден.
        HTTPException: 409, если обновлённый email уже занят другим пользователем.
    """
    async with data_manager() as uow:
        user_service = UserService()
        try:
            user = await user_service.update_user(
                repository=uow.users,
                obj_id=user_id,
                user_data=user_data,
            )
            return UserOutSheme.model_validate(user)
        except UserNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )
        except Exception as ex:
            detail = str(ex)
            if "email" in detail.lower() or "exists" in detail.lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Пользователь с таким email уже существует",
                )
            raise




async def delete_user_handler(
    user_id: UUID,
    data_manager: DataManager,
) -> None:
    """
    Удаление пользователя через UserService.

    Аргументы:
        user_id (UUID): ID пользователя.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        None: Операция удаления не возвращает данные.

    Дополнительная информация:
        - Write-операция — не кэшируется.

    Возможные исключения:
        HTTPException: 404, если пользователь не найден.
    """
    async with data_manager() as uow:
        user_service = UserService()
        try:
            await user_service.delete_user(
                repository=uow.users,
                obj_id=user_id,
            )
        except UserNotFound as ex:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ex.detail,
            )