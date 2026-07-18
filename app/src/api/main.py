from fastapi import APIRouter, Depends, status, HTTPException, Path, Query
from uuid import UUID

from app.src.api.services.user_service import UserService
from app.src.api.services.team_service import TeamService
from app.src.api.services.project_service import ProjectService
from app.src.api.services.task_service import TaskService
from app.src.api.services.task_executor_service import TaskExecutorService
from app.src.api.services.event_service import EventService, MeetingService
from app.src.api.services.auth import AuthService

from app.src.api.shems import (
    UserCreateSheme,
    UserUpdateSheme,
    UserOutSheme,
    TeamSchema,
    ProjectSchema,
    TaskOutSheme,
    TaskExecutorOutSheme,
    EventSheme,
    MeetingSheme,
    EventCreate,
    MeetingCreate,
)

from app.src.dal.database.session_manage import DataBaseManager, UnitOfWork
from app.src.dal.database.engine import start_engine




api_router = APIRouter()



# # === Команды ===
# @api_router.post("/teams", status_code=status.HTTP_201_CREATED, response_model=TeamSchema)
# async def create_team(
#     name: str,
#     manager_id: UUID,
#     team_service: TeamService = Depends(get_team_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Создаёт команду и назначает менеджера.

#     Возвращает:
#         TeamSchema: Созданная команда.

#     Исключения:
#         400: Если команда уже существует.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             team = await team_service.create_team(
#                 team_repo=uow.teams,
#                 user_repo=uow.users,
#                 name=name,
#                 manager_id=manager_id,
#             )
#         return team
#     except Exception as ex:
#         raise HTTPException(status_code=400, detail=f"Ошибка создания команды: {ex}")


# @api_router.get("/teams/{team_id}", response_model=TeamSchema)
# async def get_team(
#     team_id: UUID = Path(..., description="ID команды"),
#     team_service: TeamService = Depends(get_team_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Получает команду по ID.

#     Возвращает:
#         TeamSchema: Данные команды.

#     Исключения:
#         404: Если команда не найдена.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             team = await team_service.get_team_by_id(
#                 team_repo=uow.teams,
#                 team_id=team_id,
#             )
#         return team
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Команда не найдена: {ex}")


# @api_router.get("/teams/{team_id}/members", response_model=list[UserOutSheme])
# async def get_team_members(
#     team_id: UUID = Path(..., description="ID команды"),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Получает всех участников команды.

#     Возвращает:
#         list[UserOutSheme]: Список пользователей.

#     Исключения:
#         404: Если команда не найдена.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             team = await uow.teams.get_by_id(team_id)
#             if not team:
#                 raise HTTPException(status_code=404, detail="Команда не найдена")
#             users = await uow.users.get_all()
#             return [u for u in users if u.team_id == team_id]
#     except HTTPException:
#         raise
#     except Exception as ex:
#         raise HTTPException(status_code=400, detail=f"Ошибка получения участников: {ex}")


# # === Проекты ===
# @api_router.post("/projects", status_code=status.HTTP_201_CREATED, response_model=ProjectSchema)
# async def create_project(
#     name: str,
#     description: str | None = None,
#     team_ids: list[UUID] | None = None,
#     project_service: ProjectService = Depends(get_project_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Создаёт проект и привязывает его к командам.

#     Возвращает:
#         ProjectSchema: Созданный проект.

#     Исключения:
#         400: Если проект уже существует.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             project = await project_service.create_project(
#                 project_repo=uow.projects,
#                 team_repo=uow.teams,
#                 name=name,
#                 description=description,
#                 team_ids=team_ids,
#             )
#         return project
#     except Exception as ex:
#         raise HTTPException(status_code=400, detail=f"Ошибка создания проекта: {ex}")


# @api_router.get("/projects/{project_id}", response_model=ProjectSchema)
# async def get_project(
#     project_id: UUID = Path(..., description="ID проекта"),
#     project_service: ProjectService = Depends(get_project_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Получает проект по ID.

#     Возвращает:
#         ProjectSchema: Данные проекта.

#     Исключения:
#         404: Если проект не найден.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             project = await project_service.get_project_by_id(
#                 project_repo=uow.projects,
#                 project_id=project_id,
#             )
#         return project
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Проект не найден: {ex}")


# @api_router.get("/projects/{project_id}/teams", response_model=list[TeamSchema])
# async def get_project_teams(
#     project_id: UUID = Path(..., description="ID проекта"),
#     project_service: ProjectService = Depends(get_project_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Получает команды, участвующие в проекте.

#     Возвращает:
#         list[TeamSchema]: Список команд.

#     Исключения:
#         404: Если проект не найден.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             teams = await project_service.get_projects_for_team(
#                 project_repo=uow.projects,
#                 team_id=project_id,
#             )
#         return teams
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Проект не найден: {ex}")


# # === Задачи ===
# @api_router.post("/teams/{team_id}/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskOutSheme)
# async def create_task(
#     team_id: UUID = Path(..., description="ID команды"),
#     name: str,
#     description: str | None = None,
#     priority: str = "medium",
#     parent_id: UUID | None = None,
#     executor_ids: list[UUID] | None = None,
#     task_service: TaskService = Depends(get_task_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Создаёт задачу в команде.

#     Возвращает:
#         TaskOutSheme: Созданная задача.

#     Исключения:
#         400: Если команда не найдена.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             task = await task_service.create_task(
#                 task_repo=uow.tasks,
#                 task_executor_repo=uow.task_executors,
#                 team_repo=uow.teams,
#                 user_id=None,  # Заглушка — в реальном проекте: current_user.id
#                 team_id=team_id,
#                 name=name,
#                 description=description,
#                 priority=priority,
#                 parent_id=parent_id,
#                 executor_ids=executor_ids,
#             )
#         return TaskOutSheme.model_validate(task)
#     except Exception as ex:
#         raise HTTPException(status_code=400, detail=f"Ошибка создания задачи: {ex}")


# @api_router.get("/teams/{team_id}/tasks", response_model=list[TaskOutSheme])
# async def list_tasks(
#     team_id: UUID = Path(..., description="ID команды"),
#     priority: str | None = None,
#     task_service: TaskService = Depends(get_task_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Получает задачи команды с фильтрацией по приоритету.

#     Возвращает:
#         list[TaskOutSheme]: Список задач.

#     Исключения:
#         404: Если команда не найдена.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             tasks = await task_service.list_tasks(
#                 task_repo=uow.tasks,
#                 team_id=team_id,
#                 priority=priority,
#             )
#         return [TaskOutSheme.model_validate(t) for t in tasks]
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Команда не найдена: {ex}")


# @api_router.put("/teams/{team_id}/tasks/{task_id}", response_model=TaskOutSheme)
# async def update_task(
#     team_id: UUID = Path(..., description="ID команды"),
#     task_id: UUID = Path(..., description="ID задачи"),
#     name: str | None = None,
#     description: str | None = None,
#     priority: str | None = None,
#     task_service: TaskService = Depends(get_task_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Обновляет задачу.

#     Возвращает:
#         TaskOutSheme: Обновлённая задача.

#     Исключения:
#         404: Если задача не найдена.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             task = await task_service.update_task(
#                 task_repo=uow.tasks,
#                 task_id=task_id,
#                 name=name,
#                 description=description,
#                 priority=priority,
#             )
#         return TaskOutSheme.model_validate(task)
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Задача не найдена: {ex}")


# @api_router.delete("/teams/{team_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_task(
#     team_id: UUID = Path(..., description="ID команды"),
#     task_id: UUID = Path(..., description="ID задачи"),
#     task_service: TaskService = Depends(get_task_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Удаляет задачу.

#     Исключения:
#         404: Если задача не найдена.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             await task_service.delete_task(
#                 task_repo=uow.tasks,
#                 task_id=task_id,
#             )
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Задача не найдена: {ex}")
# api_router = APIRouter()


# # ... предыдущие эндпоинты ...

# @api_router.post("/tasks/{task_id}/executors", status_code=status.HTTP_201_CREATED, response_model=TaskExecutorOutSheme)
# async def add_executor(
#     task_id: UUID = Path(..., description="Уникальный идентификатор задачи"),
#     user_id: UUID = Body(..., description="Уникальный идентификатор пользователя-исполнителя"),
#     estimate: int | None = Body(default=None, description="Оценка времени исполнителя (в часах или пунктах)"),
#     task_executor_service: TaskExecutorService = Depends(get_task_executor_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Добавляет исполнителя к задаче.

#     Аргументы:
#         task_id (UUID): ID задачи.
#         user_id (UUID): ID пользователя.
#         estimate (int | None): Оценка (опционально).

#     Возвращает:
#         TaskExecutorOutSheme: Созданная связка "задача-исполнитель".

#     Исключения:
#         HTTPException(400): Ошибка добавления исполнителя (дубликат, отсутствие задачи/пользователя).
#     """
#     try:
#         async with db_manager.uof() as uow:
#             executor = await task_executor_service.add_executor(
#                 task_repo=uow.tasks,
#                 task_executor_repo=uow.task_executors,
#                 task_id=task_id,
#                 user_id=user_id,
#                 estimate=estimate,
#             )
#         return executor
#     except HTTPException:
#         raise
#     except Exception as ex:
#         raise HTTPException(status_code=400, detail=f"Ошибка добавления исполнителя: {ex}")


# @api_router.delete("/tasks/{task_id}/executors/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def remove_executor(
#     task_id: UUID = Path(..., description="Уникальный идентификатор задачи"),
#     user_id: UUID = Path(..., description="Уникальный идентификатор пользователя-исполнителя"),
#     task_executor_service: TaskExecutorService = Depends(get_task_executor_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Удаляет исполнителя из задачи.

#     Исключения:
#         HTTPException(404): Связка задача-исполнитель не найдена.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             await task_executor_service.remove_executor(
#                 task_executor_repo=uow.task_executors,
#                 task_id=task_id,
#                 user_id=user_id,
#             )
#     except HTTPException:
#         raise
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Связка задача-исполнитель не найдена: {ex}")


# @api_router.put("/tasks/{task_id}/executors/{user_id}/estimate", response_model=TaskExecutorOutSheme)
# async def update_executor_estimate(
#     task_id: UUID = Path(..., description="Уникальный идентификатор задачи"),
#     user_id: UUID = Path(..., description="Уникальный идентификатор пользователя-исполнителя"),
#     estimate: int = Body(..., description="Новая оценка времени (целое число)"),
#     task_executor_service: TaskExecutorService = Depends(get_task_executor_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Обновляет оценку исполнителя.

#     Аргументы:
#         estimate (int): Новая оценка времени.

#     Возвращает:
#         TaskExecutorOutSheme: Обновлённая связка.

#     Исключения:
#         HTTPException(404): Связка не найдена.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             executor = await task_executor_service.update_estimate(
#                 task_executor_repo=uow.task_executors,
#                 task_id=task_id,
#                 user_id=user_id,
#                 estimate=estimate,
#             )
#         return executor
#     except HTTPException:
#         raise
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Ошибка обновления оценки: {ex}")


# @api_router.get("/tasks/{task_id}/executors", response_model=List[TaskExecutorOutSheme])
# async def get_executors_for_task(
#     task_id: UUID = Path(..., description="Уникальный идентификатор задачи"),
#     task_executor_service: TaskExecutorService = Depends(get_task_executor_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
# ):
#     """
#     Получает всех исполнителей задачи.

#     Возвращает:
#         List[TaskExecutorOutSheme]: Список исполнителей.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             executors = await task_executor_service.get_executors_for_task(
#                 task_executor_repo=uow.task_executors,
#                 task_id=task_id,
#             )
#         return executors
#     except Exception as ex:
#         raise HTTPException(status_code=404, detail=f"Задача не найдена: {ex}")
    
# @api_router.get("/users/me/tasks", response_model=List[TaskOutSheme])
# async def get_user_tasks(
#     page: int = Query(default=1, ge=1, description="Номер страницы"),
#     page_size: int = Query(default=10, ge=1, le=100, description="Размер страницы"),
#     task_executor_service: TaskExecutorService = Depends(get_task_executor_service),
#     db_manager: DataBaseManager = Depends(get_db_manager),
#     current_user: UUID = Depends(get_current_user),
# ):
#     """
#     Получает все задачи текущего пользователя с пагинацией.

#     Возвращает:
#         List[TaskOutSheme]: Список задач.

#     Исключения:
#         HTTPException(404): Если пользователь не найден.
#     """
#     try:
#         async with db_manager.uof() as uow:
#             tasks, _ = await task_executor_service.get_tasks_for_user(
#                 task_executor_repo=uow.task_executors,
#                 user_id=current_user,
#                 page=page,
#                 page_size=page_size,
#             )
#         return [TaskOutSheme.model_validate(t) for t in tasks]
#     except HTTPException:
#         raise
#     except Exception as ex:
#         raise HTTPException(status_code=500, detail=f"Ошибка получения задач пользователя: {ex}")