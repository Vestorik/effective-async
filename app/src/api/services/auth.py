
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

from datetime import datetime, timedelta, timezone
from logging import getLogger
from uuid import UUID

from jwt import PyJWTError, decode, encode
from passlib.context import CryptContext

from app.src.api.exceptions import InvalidCredentials, UserNotFound
from app.src.api.shems import UserCreateSheme, UserOutSheme
from app.src.dal.database.models import UserModel

from app.src.dal.database.repositories import UserRepository

logger = getLogger(__name__)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


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

    def __init__(self, secret_key: str, token_expiry_minutes: int = 60):
        self.secret_key = secret_key
        self.token_expiry_minutes = token_expiry_minutes

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
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
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

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.token_expiry_minutes)
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