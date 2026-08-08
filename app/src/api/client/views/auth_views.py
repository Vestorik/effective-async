from datetime import datetime
from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError, EmailStr, BaseModel

from app.src.api.api_utils import DependsDataManager
from app.src.api.exceptions import InvalidCredentials, UserAlreadyExists
from app.src.api.handlers.user_handlers import create_user_handler
from app.src.api.services.auth import AuthService
from app.src.api.shems import UserCreateSheme
from app.src.api.client.views._views_base import templates, prefix

auth_router_views = APIRouter(prefix=f"{prefix}/auth", tags=["auth"])
logger = getLogger(__name__)

@auth_router_views.get("/register")
async def register_get(
    request: Request,
    error: dict | None = None,
):
    """
    Отображение формы регистрации.

    Аргументы:
        request (Request): Объект запроса FastAPI.
        error (dict): Словарь с ошибками валидации от предыдущего POST запроса.

    Возвращает:
        Response: Срендеренную страницу регистрации.
    """
    return templates.TemplateResponse(
        name="auth/registration_template.html",
        request=request, context={"errors": error or {}},
        status_code=status.HTTP_200_OK
    )


@auth_router_views.post("/register", response_class=RedirectResponse)
async def register_post(
    request: Request,
    data_manager: DependsDataManager,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    """
    Обработка регистрации нового пользователя.

    Аргументы:
        request (Request): Объект запроса.
        username (str): Имя пользователя из формы.
        email (str): Email из формы.
        password (str): Пароль из формы.
        confirm_password (str): Подтверждение пароля.
        data_manager (DataManager): Внедрённый менеджер данных (UoW).

    Возвращает:
        RedirectResponse: Перенаправление на страницу входа при успехе.
        Response: Та же страница регистрации с ошибками при неудаче.
    """
    # Валидация входящих данных через Pydantic
    try:
        if password != confirm_password:
            return templates.TemplateResponse(
                name="auth/registration_template.html",
                request=request,
                context={"errors": {"password": "Пароли не совпадают"}},
            )

        
        user_data = UserCreateSheme(
            username=username,
            email=email,
            password=password,
            role="user",  # По умолчанию роль user
            team_id=None
        )
        await create_user_handler(user_data, data_manager) 
        
        return RedirectResponse(
            url=f"{prefix}/auth/login",
            status_code = status.HTTP_303_SEE_OTHER,
        )
        
    except ValidationError:

        return templates.TemplateResponse(
            name="auth/registration_template.html",
            request=request, 
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        
    except UserAlreadyExists:
        return templates.TemplateResponse(
            name="auth/registration_template.html",
            request=request, 
            context={"errors": {"email": "Пользователь с таким email уже существует"}},
            status_code=status.HTTP_409_CONFLICT
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Ошибка регистрации: {e}")
        return templates.TemplateResponse(
            name="auth/registration_template.html",
            request= request, 
            context={"errors": {"general": "Произошла ошибка при регистрации. Попробуйте позже."}},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@auth_router_views.get("/login")
async def login_get(request: Request):
    """
    Отображение формы входа.

    Аргументы:
        request (Request): Объект запроса.

    Возвращает:
        Response: Срендеренную страницу входа.
    """
    return templates.TemplateResponse(
        name="auth/login_template.html",
        request=request, 
        context={ "errors": {}, "success": ""}
    )

class LoginRequest(BaseModel):
    """
    Схема валидации данных для входа.

    Содержит поля email и password с базовой валидацией.
    """
    email: EmailStr
    password: str


@auth_router_views.post("/login")
async def login_post(
    request: Request,
    data_manager: DependsDataManager,
    login_data: Annotated[LoginRequest, Form()],
):
    """
    Обработка входа пользователя.

    Аргументы:
        request (Request): Объект запроса.
        data_manager (DataManager): Внедрённый менеджер данных.

    Возвращает:
        RedirectResponse: Перенаправление на главную страницу или дашборд.
        Response: Та же страница входа с ошибкой.
    """
    async with data_manager() as uow:
        auth_service = AuthService()

        try:
            # Генерация токенов
            tokens: dict[str, str | int] = await auth_service.authenticate(
                user_repo=uow.users,
                email=login_data.email,
                password=login_data.password
            )
            
            redirect_response = RedirectResponse(
                url=f"{prefix}/dashboard", 
                status_code=status.HTTP_303_SEE_OTHER
            )
            
            # Устанавливаем куки напрямую на ответ редиректа
            redirect_response.set_cookie(
                key="access_token",
                value=tokens["access_token"],  # ty:ignore[invalid-argument-type]
                httponly=True,
                secure=True,       
                samesite="lax",   
                max_age=tokens["durationin_sec"]  # ty:ignore[invalid-argument-type]
            )

            return redirect_response

        except InvalidCredentials:
             return templates.TemplateResponse(
                name="auth/login_template.html",
                request=request, context={"errors": {"general": "Неверный email или пароль"}},
                status_code=status.HTTP_200_OK # Используем 200 для формы, фронтенд покажет ошибку
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Ошибка входа: {e}")
            return templates.TemplateResponse(
                name="auth/login_template.html",
                request=request, context={"errors": {"general": "Произошла ошибка при входе. Попробуйте позже."}},
                status_code=status.HTTP_200_OK
            )
            
            
@auth_router_views.get("/logout")
async def logout(
    request: Request,
):
    """
    Выход пользователя из системы.

    Описание:
        Удаляет токен доступа из куки браузера пользователя и перенаправляет
        на страницу входа.

    Аргументы:
        request (Request): Объект запроса FastAPI.

    Возвращает:
        RedirectResponse: Перенаправление на страницу входа после очистки сессии.
    """
    response = RedirectResponse(url=f"{prefix}/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,      
        samesite="lax",    
        path="/"           
    )
    
    return response