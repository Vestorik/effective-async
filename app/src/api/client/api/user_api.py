from uuid import UUID

from fastapi import APIRouter, Path, status

from app.src.api.utils.api_utils import DependsDataManager
from app.src.api.handlers.user_handlers import (
    create_user_handler,
    delete_user_handler,
    get_user_handler,
    update_user_handler,
)
from app.src.api.shems import UserCreateSheme, UserOutSheme, UserUpdateSheme

user_router = APIRouter(prefix="/users")


# === Пользователи ===
@user_router.post(
    "",
    response_model=UserOutSheme,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя",
    description="Создаёт нового пользователя. Валидация уникальности email и хэширование пароля выполняются на стороне обработчика.",
    responses={
        201: {"description": "Пользователь успешно создан"},
        400: {"description": "Некорректные данные или email уже занят"},
        409: {"description": "Конфликт (например, дубликат email)"},
    },
)
async def create_user_api(
    user_data: UserCreateSheme,
    db_manager: DependsDataManager,
):
    """
    API-обёртка для создания пользователя.

    Аргументы:
        user_data (UserCreateSheme): Данные пользователя.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        UserOutSheme: Созданный пользователь (без пароля).
    """
    return await create_user_handler(user_data, db_manager)



@user_router.get(
    "/{user_id}",
    response_model=UserOutSheme,
    status_code=status.HTTP_200_OK,
    summary="Получить пользователя по ID",
    description="Возвращает пользователя с указанным ID. Данные кэшируются в Redis на 10 минут.",
    responses={
        200: {"description": "Пользователь найден"},
        404: {"description": "Пользователь не найден"},
    },
)
async def get_user_api(
    db_manager: DependsDataManager,
    user_id: UUID = Path(..., description="ID пользователя"),
    
):
    """
    API-обёртка для получения пользователя по ID.

    Аргументы:
        user_id (UUID): ID пользователя.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        UserOutSheme: Данные пользователя.
    """
    return await get_user_handler(user_id, db_manager)


@user_router.patch(
    "/{user_id}",
    response_model=UserOutSheme,
    status_code=status.HTTP_200_OK,
    summary="Обновить пользователя",
    description="Частичное обновление данных пользователя. Не кэшируется (изменяет состояние).",
    responses={
        200: {"description": "Пользователь успешно обновлён"},
        404: {"description": "Пользователь не найден"},
    },
)
async def update_user_api(
    user_data: UserUpdateSheme,
    db_manager: DependsDataManager,
    user_id: UUID = Path(..., description="ID пользователя"),
):
    """
    API-обёртка для обновления пользователя.

    Аргументы:
        user_id (UUID): ID пользователя.
        user_data (UserUpdateSheme): Обновляемые данные.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        UserOutSheme: Обновлённый пользователь.
    """
    return await update_user_handler(user_id, user_data, db_manager)


@user_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить пользователя",
    description="Удаляет пользователя по ID. Не кэшируется (изменяет состояние).",
    responses={
        204: {"description": "Пользователь удалён"},
        404: {"description": "Пользователь не найден"},
    },
)
async def delete_user_api(
    data_manager: DependsDataManager,
    user_id: UUID = Path(..., description="ID пользователя"),
):
    """
    API-обёртка для удаления пользователя.

    Аргументы:
        user_id (UUID): ID пользователя.
        data_manager (DependsDataManager): Внедрённый менеджер данных.

    Возвращает:
        None: Пустой ответ со статусом 204.
    """
    return await delete_user_handler(user_id, data_manager)
