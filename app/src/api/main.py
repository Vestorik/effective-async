from fastapi import APIRouter
from app.src.api.handlers.event_handlers import event_router
from app.src.api.handlers.project_handlers import project_router
from app.src.api.handlers.task_executor_handlers import task_executor_router
from app.src.api.handlers.task_handlers import task_router
from app.src.api.handlers.team_handlers import team_router
from app.src.api.handlers.user_handlers import user_router


api_routers: list[APIRouter] = [
event_router,
project_router,
task_executor_router,
task_router,
team_router,
user_router,
]
