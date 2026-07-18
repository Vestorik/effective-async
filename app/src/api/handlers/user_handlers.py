from fastapi import APIRouter, status, HTTPException, Path
from uuid import UUID
from app.src.api.services.user_service import UserService
from app.src.api.shems import UserCreateSheme, UserUpdateSheme, UserOutSheme

from app.src.api.api_utils import DependsDataManager

user_router = APIRouter(prefix="/users")


# === Пользователи ===
@user_router.post(
    "/users", status_code=status.HTTP_201_CREATED, response_model=UserOutSheme
)
async def create_user(
    db_manager: DependsDataManager,
    user_data: UserCreateSheme,
    user_service: UserService = UserService(),
):
    """
    Создаёт нового пользователя.

    Валидация:
        - Pydantic: username, email, password (через UserCreateSheme).
        - Сервис: уникальность email, хэширование пароля.

    Ограничения:
        - Проверка прав (admin) — в реальном проекте через Depends.

    Возвращает:
        UserOutSheme: Созданный пользователь (без пароля).
    """
    try:
        async with db_manager() as uow:
            user = await user_service.create(
                repository=uow.users,
                obj=user_data,
            )
        return user
    except Exception as ex:
        raise HTTPException(
            status_code=400, detail=f"Ошибка создания пользователя: {ex}"
        )


@user_router.get("/users/{user_id}", response_model=UserOutSheme)
async def get_user(
    db_manager: DependsDataManager,
    user_id: UUID = Path(..., description="ID пользователя"),
    user_service: UserService = UserService(),
):
    """
    Получает пользователя по ID.

    Возвращает:
        UserOutSheme: Данные пользователя.

    Исключения:
        404: Если пользователь не найден.
    """
    try:
        async with db_manager() as uow:
            user = await user_service.get_user_by_id(
                repository=uow.users,
                obj_id=user_id,
            )
        return user
    except Exception as ex:
        raise HTTPException(status_code=404, detail=f"Пользователь не найден: {ex}")


@user_router.patch("/users/{user_id}", response_model=UserOutSheme)
async def update_user(
    db_manager: DependsDataManager,
    user_data: UserUpdateSheme,
    user_id: UUID = Path(..., description="ID пользователя"),
    user_service: UserService = UserService(),
):
    """
    Обновляет данные пользователя.

    Возвращает:
        UserOutSheme: Обновлённый пользователь.

    Исключения:
        404: Если пользователь не найден.
    """
    try:
        async with db_manager() as uow:
            user = await user_service.update_user(
                repository=uow.users,
                obj_id=user_id,
                user_data=user_data,
            )
        return user
    except Exception as ex:
        raise HTTPException(status_code=404, detail=f"Пользователь не найден: {ex}")


@user_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    db_manager: DependsDataManager,
    user_id: UUID = Path(..., description="ID пользователя"),
    user_service: UserService = UserService(),
):
    """
    Удаляет пользователя.

    Исключения:
        404: Если пользователь не найден.
    """
    try:
        async with db_manager() as uow:
            await user_service.delete_user(
                repository=uow.users,
                obj_id=user_id,
            )
    except Exception as ex:
        raise HTTPException(status_code=404, detail=f"Пользователь не найден: {ex}")
