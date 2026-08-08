from fastapi import APIRouter

from app.src.api.client.api.event_api import event_router
from app.src.api.client.api.project_api import project_router
from app.src.api.client.api.task_api import task_router
from app.src.api.client.api.task_executor_api import task_executor_router
from app.src.api.client.api.team_api import team_router
from app.src.api.client.api.user_api import user_router
from app.src.api.client.views.auth_views import auth_router_views
from app.src.api.client.views.other_views import (
    dashboard_router_views,
    task_router_views,
    team_router_views,
)

api_routers: list[APIRouter] = [
event_router,
project_router,
task_executor_router,
task_router,
team_router,
user_router,
auth_router_views,
dashboard_router_views,
team_router_views,
task_router_views
]
