from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.src.api.client.views._views_base import templates, prefix

from app.src.api.api_utils import DependsDataManager
from app.src.api.exceptions import TaskNotFound, TeamNotFound
from app.src.api.services.auth import RoleType, require_permissions
from app.src.api.services.dashboard_service import DashboardService
from app.src.api.services.task_service import TaskService
from app.src.api.services.team_service import TeamService
from app.src.api.shems import TaskWithExecutorsOutSheme

logger = getLogger(__name__)


task_router_views = APIRouter(prefix=f"{prefix}/tasks", tags=["tasks"])
team_router_views = APIRouter(prefix=f"{prefix}/teams", tags=["teams"])
dashboard_router_views = APIRouter(prefix=f"{prefix}/dashboard", tags=["dashboard"])



@dashboard_router_views.get("/", response_class=HTMLResponse)
async def dashboard_view(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
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
                name="index.html",
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


@team_router_views.get("/", response_class=HTMLResponse)
async def teams_list(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
):
    """
    Отображение списка всех команд.

    Аргументы:
        request: Объект запроса.
        data_manager: Менеджер данных (UoW).
        current_user: UUID текущего пользователя.

    Возвращает:
        Response: Страница со списком команд.
    """
    try:
        async with data_manager() as uow:
            team_service = TeamService()
            teams = await team_service.get_all_teams(team_repo=uow.teams)

            return templates.TemplateResponse(
                name=f"{prefix}pages/teams/list.html",
                request=request,
                context={"teams": teams, "current_user_id": str(current_user_id)},
            )
    except Exception as e:
        logger.error(f"Ошибка загрузки списка команд: {e}")
        raise HTTPException(status_code=500, detail="Не удалось загрузить команды")


@team_router_views.get("/{team_id}", response_class=HTMLResponse)
async def team_detail(
    request: Request,
    team_id: UUID,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
):
    """
    Детальная информация о команде.

    Аргументы:
        request: Объект запроса.
        team_id: ID команды.
        data_manager: Менеджер данных (UoW).
        current_user: UUID текущего пользователя.

    Возвращает:
        Response: Страница с деталями команды.
    """
    try:
        async with data_manager() as uow:
            team_service = TeamService()
            team = await team_service.get_team_by_id(
                team_repo=uow.teams, team_id=team_id
            )

            # Здесь можно также получить участников, если есть ссылка в модели
            # для примера просто передаем team

            return templates.TemplateResponse(
                request=request,
                name=f"{prefix}pages/teams/detail.html",
                context={"team": team, "current_user_id": str(current_user_id)},
            )
    except TeamNotFound:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    except Exception as e:
        logger.error(f"Ошибка загрузки деталей команды: {e}")
        raise HTTPException(
            status_code=500, detail="Не удалось загрузить данные команды"
        )


@team_router_views.post("/create", response_class=RedirectResponse)
async def create_team(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
    name: str = Form(...),
):
    """
    Создание новой команды.

    Аргументы:
        request: Объект запроса.
        name: Название команды.
        data_manager: Менеджер данных (UoW).
        current_user: UUID пользователя-создателя.

    Возвращает:
        RedirectResponse: Перенаправление на список команд.
    """
    try:
        async with data_manager() as uow:
            team_service = TeamService()
            await team_service.create_team(
                team_repo=uow.teams,
                user_repo=uow.users,
                name=name,
                manager_id=current_user_id,
            )
    except Exception as e:
        logger.error(f"Ошибка создания команды: {e}")
        # В реальном приложении нужно передать ошибку в контекст шаблона
        # Но так как мы перенаправляем, будем считать успехом для MVP

    return RedirectResponse(url="/views/teams", status_code=status.HTTP_303_SEE_OTHER)


@team_router_views.post("/join", response_class=RedirectResponse)
async def join_team(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
    team_id: UUID = Form(...),
):
    """
    Вступление в команду.

    Аргументы:
        request: Объект запроса.
        team_id: ID команды.
        data_manager: Менеджер данных (UoW).
        current_user: UUID пользователя.

    Возвращает:
        RedirectResponse: Перенаправление на детальные данные команды.
    """
    try:
        async with data_manager() as uow:
            team_service = TeamService()
            await team_service.join_team(
                team_repo=uow.teams,
                user_repo=uow.users,
                user_id=current_user_id,
                team_id=team_id,
            )
    except TeamNotFound:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка вступления в команду: {e}")
        raise HTTPException(status_code=500, detail="Не удалось вступить в команду")

    return RedirectResponse(
        url=f"/views/teams/{team_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@task_router_views.get("/", response_class=HTMLResponse)
async def tasks_list(
    request: Request,
    data_manager: DependsDataManager,
    team_id: UUID,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
    priority: str | None = Form(None),
):
    """
    Отображение списка задач для команды.

    Аргументы:
        request: Объект запроса.
        data_manager: Менеджер данных (UoW).
        team_id: UUID ID команды.
        priority: Опциональный фильтр по приоритету.
        current_user_id: ID текущего пользователя.

    Возвращает:
        Response: Страница со списком задач.
    """
    try:
        async with data_manager() as uow:
            task_service = TaskService()

            # Получаем задачи через сервис
            tasks = await task_service.list_tasks(
                task_repo=uow.tasks, team_id=team_id, priority=priority
            )

            task_shemes = [
                TaskWithExecutorsOutSheme.model_validate(t)
                for t in tasks
                if hasattr(t, "executors")  # Убедимся, что executors загружены
            ]

            # Если executors не загружены в модели (selectinload), добавим их вручную здесь для отображения
            enriched_tasks = []
            for task in tasks:
                # Загружаем исполнителей для каждой задачи
                executors = await uow.task_executors.get_executors_for_task(task.id)
                task_with_exec = TaskWithExecutorsOutSheme(
                    name=task.name,
                    description=task.description,
                    executors=executors,
                )
                enriched_tasks.append(task_with_exec)

            return templates.TemplateResponse(
                name=f"{prefix}pages/tasks/list.html",
                context={
                    "tasks": enriched_tasks,
                    "team_id": str(team_id),
                    "current_user_id": str(current_user_id),
                    "priority_filter": priority,
                },
                request=request,
            )
    except TeamNotFound:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    except Exception as e:
        logger.error(f"Ошибка загрузки списка задач: {e}")
        raise HTTPException(status_code=500, detail="Не удалось загрузить задачи")


@task_router_views.get("/{task_id}", response_class=HTMLResponse)
async def task_detail(
    request: Request,
    task_id: UUID,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
):
    """
    Детальная информация о задаче.

    Аргументы:
        request: Объект запроса.
        task_id: UUID ID задачи.
        data_manager: Менеджер данных (UoW).
        current_user_id: ID текущего пользователя.

    Возвращает:
        Response: Страница с деталями задачи.
    """
    try:
        async with data_manager() as uow:
            task_service = TaskService()

            # Получаем задачу
            task = await uow.tasks.get_by_id(task_id)
            if not task:
                raise TaskNotFound()

            # Получаем исполнителей
            executors = await uow.task_executors.get_executors_for_task(task.id)  # ty:ignore[invalid-argument-type]

            task_sheme = TaskWithExecutorsOutSheme(
                name=task.name,
                description=task.description,
                project_id=task.project_id,
                parent_id=task.parent_id,
                executors=executors,
            )

            return templates.TemplateResponse(
                name=f"{prefix}pages/tasks/detail.html",
                context={"task": task_sheme, "current_user_id": str(current_user_id)},
                request=request,
            )
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    except Exception as e:
        logger.error(f"Ошибка загрузки деталей задачи: {e}")
        raise HTTPException(
            status_code=500, detail="Не удалось загрузить детали задачи"
        )


@task_router_views.post("/create", response_class=RedirectResponse)
async def create_task(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
    team_id: UUID = Form(...),
    name: str = Form(...),
    description: str | None = Form(None),
    priority: str = Form("medium"),
    parent_id: UUID | None = Form(None),
    executor_ids: list[UUID] | None = Form(None),
):
    """
    Создание новой задачи.

    Аргументы:
        request: Объект запроса.
        data_manager: Менеджер данных (UoW).
        team_id: UUID ID команды.
        name: Название задачи.
        description: Описание задачи.
        priority: Приоритет (low, medium, high).
        parent_id: ID родительской задачи.
        executor_ids: Список ID исполнителей.
        current_user_id: ID пользователя-создателя.

    Возвращает:
        RedirectResponse: Перенаправление на список задач.
    """
    try:
        async with data_manager() as uow:
            task_service = TaskService()

            # Валидация командных прав через сервис (упрощенно)
            # TaskService.create_task сам проверит TeamNotFound

            await task_service.create_task(
                task_repo=uow.tasks,
                task_executor_repo=uow.task_executors,
                team_repo=uow.teams,
                user_id=current_user_id,
                team_id=team_id,
                name=name,
                description=description,
                priority=priority,
                parent_id=parent_id,
                executor_ids=executor_ids,
            )

    except TeamNotFound:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    except Exception as e:
        logger.error(f"Ошибка создания задачи: {e}")
        raise HTTPException(status_code=400, detail="Не удалось создать задачу")

    return RedirectResponse(
        url=f"/views/tasks/?team_id={team_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@task_router_views.post("/update/{task_id}", response_class=RedirectResponse)
async def update_task(
    request: Request,
    task_id: UUID,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
    name: str = Form(...),
    description: str | None = Form(None),
):
    """
    Обновление задачи.

    Аргументы:
        request: Объект запроса.
        task_id: UUID ID задачи.
        data_manager: Менеджер данных (UoW).
        name: Новое название.
        description: Новое описание.
        current_user_id: ID пользователя.

    Возвращает:
        RedirectResponse: Перенаправление на детали задачи.
    """
    try:
        async with data_manager() as uow:
            task_service = TaskService()

            await task_service.update_task(
                task_repo=uow.tasks, task_id=task_id, name=name, description=description
            )

    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    except Exception as e:
        logger.error(f"Ошибка обновления задачи: {e}")
        raise HTTPException(status_code=400, detail="Не удалось обновить задачу")

    return RedirectResponse(
        url=f"/views/tasks/{task_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@task_router_views.post("/delete/{task_id}", response_class=RedirectResponse)
async def delete_task(
    request: Request,
    task_id: UUID,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
):
    """
    Удаление задачи.

    Аргументы:
        request: Объект запроса.
        task_id: UUID ID задачи.
        data_manager: Менеджер данных (UoW).
        current_user_id: ID пользователя.

    Возвращает:
        RedirectResponse: Перенаправление на список задач (предположительно).
    """
    try:
        async with data_manager() as uow:
            task_service = TaskService()

            await task_service.delete_task(task_repo=uow.tasks, task_id=task_id)

    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    except Exception as e:
        logger.error(f"Ошибка удаления задачи: {e}")
        raise HTTPException(status_code=400, detail="Не удалось удалить задачу")

    # Перенаправляем на страницу, с которой пришли (можно улучшить через referer)
    # Для MVP перенаправляем на общий список или 404 если unknown
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@task_router_views.post("/add_executor", response_class=RedirectResponse)
async def add_executor_to_task(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
    task_id: UUID = Form(...),
    user_id: UUID = Form(...),
    estimate: int | None = Form(None),
):
    """
    Добавление исполнителя к задаче.

    Аргументы:
        request: Объект запроса.
        data_manager: Менеджер данных (UoW).
        task_id: UUID ID задачи.
        user_id: UUID ID пользователя.
        estimate: Оценка исполнителя.
        current_user_id: ID пользователя (менеджера/создателя).

    Возвращает:
        RedirectResponse: Перенаправление на детали задачи.
    """
    try:
        async with data_manager() as uow:
            task_service = TaskService()

            await task_service.add_executor(
                task_repo=uow.tasks,
                task_executor_repo=uow.task_executors,
                task_id=task_id,
                user_id=user_id,
                estimate=estimate,
            )

    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    except Exception as e:
        logger.error(f"Ошибка добавления исполнителя: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(
        url=f"/views/tasks/{task_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@task_router_views.post("/update_executor_estimate", response_class=RedirectResponse)
async def update_executor_estimate(
    request: Request,
    data_manager: DependsDataManager,
    current_user_id: Annotated[
        UUID,
        Depends(
            require_permissions(role=[RoleType.USER, RoleType.MANAGER, RoleType.ADMIN])
        ),
    ],
    task_id: UUID = Form(...),
    user_id: UUID = Form(...),
    estimate: int = Form(...),
):
    """
    Обновление оценки исполнителя.

    Аргументы:
        request: Объект запроса.
        data_manager: Менеджер данных (UoW).
        task_id: UUID ID задачи.
        user_id: UUID ID пользователя.
        estimate: Новая оценка.
        current_user_id: ID пользователя.

    Возвращает:
        RedirectResponse: Перенаправление на детали задачи.
    """
    try:
        async with data_manager() as uow:
            task_service = TaskService()

            await task_service.update_executor_estimate(
                task_executor_repo=uow.task_executors,
                task_id=task_id,
                user_id=user_id,
                estimate=estimate,
            )

    except Exception as e:
        logger.error(f"Ошибка обновления оценки: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(
        url=f"/views/tasks/{task_id}", status_code=status.HTTP_303_SEE_OTHER
    )
