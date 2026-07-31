"""
Модуль аутентификации и авторизации.

Реализует:
- Регистрацию пользователя с хэшированием пароля (argon2).
- Аутентификацию по email + паролю.
- Выдачу и валидацию JWT-токенов (PyJWT).
- Принципы: DRY, DI, явная обработка исключений.

Архитектурное решение:
- Сервис принимает конкретные репозитории (UserRepository, ...) — соблюдение DI.
- Репозитории создаются в handlers.py через uow.users, uow.teams и т.д.
- Убраны явные commit/rollback — они управляются в UnitOfWork.__aexit__().
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from logging import getLogger
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends, status
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError, decode, encode
from passlib.context import CryptContext
from passlib.handlers.argon2 import argon2
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.src.api.api_utils import DependsDataManager
from app.src.api.exceptions import InvalidCredentials, UserNotFound
from app.src.api.shems import UserCreateSheme, UserOutSheme
from app.src.dal.database.models import UserModel
from app.src.dal.database.repositories import UserRepository

logger = getLogger(__name__)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class AuthConfig(BaseSettings):
    """Настройки JWT и безопасности."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / "deploy" / ".env",
        env_file_encoding="utf-8",
        extra="allow",
        env_prefix="AUTH_",
    )

    AUTH_SECRET_KEY: str = Field(..., env="AUTH_SECRET_KEY")
    AUTH_TOKEN_EXPIRY_MINUTES: int = Field(default=60, env="AUTH_TOKEN_EXPIRY_MINUTES")
    AUTH_REFRESH_TOKEN_EXPIRY_DAYS: int = Field(
        default=7, env="AUTH_REFRESH_TOKEN_EXPIRY_DAYS"
    )
    AUTH_ALGORITHM: str = "HS256"


MAIN_AUTH_CONFIG = AuthConfig()


class AuthService:
    """
    Сервис аутентификации и авторизации.

    Аргументы (при инициализации):
        secret_key (str): Ключ для JWT.
        token_expiry_minutes (int): Срок действия токена.

    Методы:
        register: Регистрирует нового пользователя.
        authenticate: Проверяет учетные данные и выдаёт JWT-токен.
        verify_token: Проверяет валидность JWT-токена.
        get_current_user: Извлекает пользователя из токена (для FastAPI Depends).
    """

    def __init__(self):
        self.secret_key = MAIN_AUTH_CONFIG.AUTH_SECRET_KEY
        self.token_expiry_minutes = MAIN_AUTH_CONFIG.AUTH_TOKEN_EXPIRY_MINUTES
        self.refresh_token_expray_days = MAIN_AUTH_CONFIG.AUTH_REFRESH_TOKEN_EXPIRY_DAYS
        self.auth_algorithm = MAIN_AUTH_CONFIG.AUTH_ALGORITHM

    async def register(
        self,
        user_repo: UserRepository,
        user_data: UserCreateSheme,
    ) -> UserOutSheme:
        """
        Регистрирует нового пользователя.

        Аргументы:
            user_repo (UserRepository): Репозиторий для работы с пользователями.
            user_data (UserCreateSheme): Данные пользователя.

        Возвращает:
            UserOutSheme: Созданный пользователь.

        Исключения:
            UserAlreadyExists: Если email уже занят.
        """
        hashed_password = pwd_context.hash(user_data.password)

        user = UserModel(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            role=user_data.role,
            team_id=user_data.team_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await user_repo.create(user)
        return UserOutSheme.model_validate(user)

    async def authenticate(
        self,
        user_repo: UserRepository,
        email: str,
        password: str,
    ) -> dict[str, str]:
        """
        Аутентифицирует пользователя и выдаёт JWT-токен.

        Аргументы:
            user_repo (UserRepository): Репозиторий для работы с пользователями.
            email (str): Email пользователя.
            password (str): Пароль.

        Возвращает:
            dict[str, str]: access_token и token_type.

        Исключения:
            InvalidCredentials: Если данные неверны.
        """
        user = await user_repo.get_by_email(email)

        if not user or not pwd_context.verify(password, user.hashed_password):
            raise InvalidCredentials()

        expires_at = datetime.now(UTC) + timedelta(
            minutes=self.token_expiry_minutes
        )
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "exp": expires_at,
        }
        token = encode(payload, self.secret_key, algorithm="HS256")
        return {"access_token": token, "token_type": "bearer"}

    async def verify_token(self, token: str) -> dict[str, str]:
        """
        Проверяет валидность JWT-токена и возвращает payload.

        Аргументы:
            token (str): JWT-токен.

        Возвращает:
            dict[str, str]: Декодированный payload.

        Исключения:
            InvalidCredentials: Если токен просрочен или неверно подписан.
        """
        try:
            payload = decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except PyJWTError as ex:
            logger.warning("Неверный JWT-токен: %s", ex)
            raise InvalidCredentials()

    async def get_current_user(
        self,
        user_repo: UserRepository,
        token: str,
    ) -> UserModel:
        """
        Извлекает пользователя из токена.

        Аргументы:
            user_repo (UserRepository): Репозиторий для работы с пользователями.
            token (str): JWT-токен.

        Возвращает:
            UserModel: Пользователь из БД.

        Исключения:
            InvalidCredentials: Если токен недействителен.
            UserNotFound: Если пользователь не найден по ID из токена.
        """
        payload = await self.verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidCredentials()
        user = await user_repo.get_by_id(UUID(user_id))
        if not user:
            raise UserNotFound()
        return user

    async def get_token_expiry(self, token: str) -> datetime:
        """
        Извлекает срок окончания действия токена (для кэширования/отображения на клиенте).

        Аргументы:
            token (str): JWT-токен.

        Возвращает:
            datetime: Дата и время окончания действия токена.

        Исключения:
            InvalidCredentials: Если токен недействителен.
        """
        try:
            payload = decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            exp = payload.get("exp")
            if not exp:
                raise InvalidCredentials()
            return datetime.fromtimestamp(exp, tz=UTC)
        except PyJWTError:
            raise InvalidCredentials()

    async def refresh_token(
        self,
        user_repo: UserRepository,
        refresh_token: str,
    ) -> dict[str, str]:
        """
        Обновляет access_token через refresh_token.

        Аргументы:
            user_repo (UserRepository): Репозиторий пользователей.
            refresh_token (str): Действующий refresh_token.

        Возвращает:
            dict[str, str]: access_token и token_type.

        Исключения:
            InvalidCredentials: Если refresh_token недействителен или не соответствует хэшу.
        """
        try:
            payload = decode(refresh_token, self.secret_key, algorithms=["HS256"])
            user_id = payload.get("sub")
            if not user_id:
                raise InvalidCredentials()
            user = await user_repo.get_by_id(UUID(user_id))
            if not user or not user.refresh_token_hash:
                raise InvalidCredentials()
            if not argon2.verify(refresh_token, user.refresh_token_hash):
                raise InvalidCredentials()

            # Генерируем новые токены
            new_access_payload = {
                "sub": str(user.id),
                "email": user.email,
                "role": user.role,
                "exp": datetime.now(UTC)
                + timedelta(minutes=self.token_expiry_minutes),
            }
            new_refresh_payload = {
                "sub": str(user.id),
                "type": "refresh",
                "exp": datetime.now(UTC) + timedelta(days=7),
            }
            new_access_token = encode(
                new_access_payload, self.secret_key, algorithm="HS256"
            )
            new_refresh_token = encode(
                new_refresh_payload, self.secret_key, algorithm="HS256"
            )

            # Обновляем хэш refresh_token в БД
            user.refresh_token_hash = argon2.hash(refresh_token)
            await user_repo.update(user)

            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
            }
        except PyJWTError:
            raise InvalidCredentials()

    async def logout(
        self,
        user_repo: UserRepository,
        user_id: UUID,
    ) -> None:
        """
        Отзывает (инвалидирует) текущий refresh_token.

        Аргументы:
            user_repo (UserRepository): Репозиторий пользователей.
            user_id (UUID): ID пользователя.

        Исключения:
            UserNotFound: Если пользователь не найден.
        """
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound()
        user.refresh_token_hash = None
        await user_repo.update(user)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user_dep(
    token: Annotated[str, Depends(oauth2_scheme)], db_manager: DependsDataManager
) -> UserModel:
    """
    Получает текущего пользователя из JWT-токена.

    Аргументы:
        token (str): JWT-токен.
        user_repo (UserRepository): Репозиторий пользователей.

    Возвращает:
        UserModel: Пользователь.

    Исключения:
        HTTPException: 401, если токен недействителен.
    """
    try:
        async with db_manager() as uow:
            auth_service = AuthService()
            return await auth_service.get_current_user(uow.users, token)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось аутентифицировать пользователя",
            headers={"WWW-Authenticate": "Bearer"},
        )


class RoleType(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    ANY = "ANY"


def require_permissions(
    # permissions: list[Permission] | None, // Реализовать в будущем
    role: list[RoleType] | None = None,
) -> Callable:

    if role is None:
        role = [
            RoleType.ANY,
        ]

    async def check_permissions(
        user_model: Annotated[UserModel, Depends(get_current_user_dep)],
    ) -> UUID:
        user_role = user_model.role
        if user_role not in [r.value for r in role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для доступа",
            )

        return user_model.id  # ty:ignore[invalid-return-type]

    return check_permissions
