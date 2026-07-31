# app/src/api/client/views/dashboard_views.py

from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.src.api.api_utils import DependsDataManager
from app.src.api.services.dashboard_service import DashboardService
from app.src.api.services.auth import RoleType, require_permissions
from app.src.api.shems import TeamWithProjectsOutSheme

logger = getLogger(__name__)

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/src/api/templates")


@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard_view(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id:  Annotated[UUID, Depends(require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN]))],
):
    """
    Отображение основной страницы дашборда.

    В левой части: список команд с количеством участников.
    В правой части: список проектов с задачами и исполнителями.
    """
    try:
        async with data_manager() as uow:
            dashboard_service = DashboardService(session=uow.session)

            teams_data = await dashboard_service.get_dashboard_data(
                user_id=current_user_id
            )

            return templates.TemplateResponse(
                name="dashboard/index.html",
                request=request,
                context={"teams": teams_data},
            )
    except Exception as e:
        logger.error(f"Ошибка загрузки дашборда: {e}")
        # В продакшене лучше перенаправлять на страницу ошибки или показывать дефолтное сообщение
        return templates.TemplateResponse(
            name="error/500.html",
            request=request,
            context={"error": "Не удалось загрузить данные дашборда"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
