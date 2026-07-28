"""
Сводка данных, необходимых для рендеринга каждого Jinja2-шаблона.

Ключи — относительные пути шаблонов относительно директории templates.
Значения — словари с описанием шаблона и списком required_context,
т.е. переменных, которые MUST быть переданы в render_template_response / render.
"""

TEMPLATES_CONTEXT = {
    # ────────────────────────────────────────────────
    #  Корневые шаблоны
    # ────────────────────────────────────────────────

    "base.html": {
        "description": (
            "Базовый шаблон для всех HTML-страниц приложения. "
            "Определяет структуру документа, навигацию, CSS-переменные, "
            "блочные секции title / head / content / scripts."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса (обязателен для Jinja2FastAPI/templates)",
            "active_page: str | None - метка текущей страницы для подсветки пункта меню ('home', 'projects', 'teams', 'tasks', 'events')",
        ],
        "blocks": ["title", "head", "content", "scripts"],
        "extends": None,
    },

    "api_docs.html": {
        "description": (
            "Страница документации API — статический справочник эндпоинтов. "
            "Контент захардкожен, контекст не требуется."
        ),
        "required_context": [],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    # ────────────────────────────────────────────────
    #  Email-шаблоны
    # ────────────────────────────────────────────────

    "email/notification.html": {
        "description": (
            "Email-уведомление о задачах. Поддерживает четыре типа: "
            "new_task, status_change, added_as_executor, updated."
        ),
        "required_context": [
            "user_name: str - имя получателя",
            "task_name: str - название задачи",
            "task_link: str - ссылка на задачу",
            "notification_type: str - тип уведомления ('new_task' | 'status_change' | 'added_as_executor' | 'updated')",
            "task_description: str | None - описание задачи (необязательно)",
            "project_name: str | None - название проекта (необязательно)",
            "team_name: str | None - название команды (необязательно)",
            "priority: str | None - приоритет ('low' | 'medium' | high') (необязательно)",
            "deadline: datetime | None - срок выполнения (необязательно)",
            "previous_status: str | None - предыдущий статус (для status_change, необязательно)",
            "new_status: str | None - новый статус (для status_change, необязательно)",
            "executor_name: str | None - имя исполнителя (для added_as_executor, необязательно)",
        ],
        "blocks": [],
        "extends": None,
    },

    "email/meeting.html": {
        "description": (
            "Email-уведомление о встречах. Поддерживает три типа: "
            "invitation, reminder, cancellation."
        ),
        "required_context": [
            "user_name: str - имя получателя",
            "meeting_name: str - название встречи",
            "meeting_link: str - ссылка на встречу",
            "notification_type: str - тип уведомления ('invitation' | 'reminder' | 'cancellation')",
            "team_name: str - название команды",
            "start_datetime: datetime - начало встречи",
            "end_datetime: datetime - конец встречи",
            "meeting_description: str | None - описание встречи (необязательно)",
            "location: str | None - место проведения (необязательно)",
            "organizer_name: str | None - имя организатора (необязательно)",
        ],
        "blocks": [],
        "extends": None,
    },

    "email/event.html": {
        "description": (
            "Email-уведомление о событиях (дедлайны, напоминания). "
            "Поддерживает два типа: event, reminder."
        ),
        "required_context": [
            "user_name: str - имя получателя",
            "event_name: str - название события",
            "event_link: str - ссылка на событие",
            "notification_type: str - тип уведомления ('event' | 'reminder')",
            "start_datetime: datetime - начало события",
            "end_datetime: datetime - конец события",
            "event_description: str | None - описание события (необязательно)",
            "event_type: str | None - тип события ('deadline' | 'reminder' | 'holiday' и т.д., необязательно)",
        ],
        "blocks": [],
        "extends": None,
    },

    # ────────────────────────────────────────────────
    #  Страницы — Главная
    # ────────────────────────────────────────────────

    "pages/index.html": {
        "description": (
            "Главная страница (дашборд). Отображает статистику, "
            "быстрые действия и мини-календарь событий."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "stats: dict - объект статистики с полями:",
            "  stats.total_projects: int - общее количество проектов",
            "  stats.total_teams: int - общее количество команд",
            "  stats.total_tasks: int - общее количество задач",
            "  stats.upcoming_events: int - событий в ближайшие 7 дней",
            "current_month: str - название текущего месяца для заголовка календаря",
            "prev_month: str - параметр предыдущего месяца (для навигации)",
            "next_month: str - параметр следующего месяца (для навигации)",
            "calendar: dict - объект календаря с полем:",
            "  calendar.days: list[dict] - дни месяца, каждый с полями number, is_today, has_event",
            "upcoming_events: list[dict] - ближайшие события, каждое с полями name, date",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    # ────────────────────────────────────────────────
    #  Страницы — Проекты
    # ────────────────────────────────────────────────

    "pages/projects/list.html": {
        "description": (
            "Страница списка проектов. Содержит карточки проектов, "
            "фильтры (поиск, команда, статус) и пагинацию."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "projects: list[Project] - список проектов, каждый с полями id, name, description, team_count, task_count, created_at",
            "teams: list[Team] - список команд для фильтра (каждый с полями id, name)",
            "pagination: Pagination - объект пагинации с полями total_pages, current_page, has_previous, has_next, prev_page, next_page, pages",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    "pages/projects/detail.html": {
        "description": (
            "Детальная страница проекта. Отображает информацию о проекте, "
            "статистику, список команд и задач."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "project: Project - объект проекта с полями id, name, description, completed_tasks, deadline",
            "teams: list[Team] - команды проекта, каждая с полями id, name, manager, users (список пользователей с полем name)",
            "tasks: list[Task] - задачи проекта, каждая с полями id, name, priority, executors (список с полем name), executor_count, deadline, status",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    # ────────────────────────────────────────────────
    #  Страницы — Команды
    # ────────────────────────────────────────────────

    "pages/teams/list.html": {
        "description": (
            "Страница списка команд. Содержит карточки команд, "
            "поиск и пагинацию."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "teams: list[Team] - список команд, каждая с полями id, name, manager_name, member_count, project_count, created_at, users (список с полем name)",
            "pagination: Pagination - объект пагинации с полями total_pages, current_page, has_previous, has_next, prev_page, next_page, pages",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    "pages/teams/detail.html": {
        "description": (
            "Детальная страница команды. Отображает информацию о команде, "
            "участников, проекты и задачи."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "team: Team - объект команды с полями id, name, created_at, member_count, project_count, task_count, manager_name, manager_email, members (список с полями name, email, is_manager)",
            "projects: list[Project] - проекты команды, каждая с полями id, name, description, created_at, task_count",
            "tasks: list[Task] - задачи команды (до 5), каждая с полями id, name, priority, deadline",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    # ────────────────────────────────────────────────
    #  Страницы — Задачи
    # ────────────────────────────────────────────────

    "pages/tasks/list.html": {
        "description": (
            "Страница списка задач. Содержит карточки задач, "
            "фильтры (приоритет, статус, команда) и пагинацию."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "tasks: list[Task] - список задач, каждая с полями id, name, description, priority, executor_count, deadline, project_name, team_name, status",
            "teams: list[Team] - список команд для фильтра (каждый с полями id, name)",
            "pagination: Pagination - объект пагинации с полями total_pages, current_page, has_previous, has_next, prev_page, next_page, pages",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    "pages/tasks/detail.html": {
        "description": (
            "Детальная страница задачи. Отображает информацию о задаче, "
            "исполнителей, подзадачи и историю изменений."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "task: Task - объект задачи с полями id, name, description, priority, status, deadline, created_at, executors (список с полями name, email, estimate), subtasks (список с полями id, name, priority, deadline), history (список с полями action, description, date, user_name)",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    # ────────────────────────────────────────────────
    #  Страницы — События
    # ────────────────────────────────────────────────

    "pages/events/list.html": {
        "description": (
            "Страница списка событий с календарём. Содержит навигацию "
            "по месяцам, фильтры (тип, команда) и пагинацию."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "events: list[Event] - список событий, каждая с полями id, name, type, description, start_datetime, end_datetime, team_name",
            "teams: list[Team] - список команд для фильтра (каждый с полями id, name)",
            "pagination: Pagination - объект пагинации с полями total_pages, current_page, has_previous, has_next, prev_page, next_page, pages",
            "current_month_name: str - название текущего месяца",
            "current_year: int - текущий год",
            "prev_month: str | int - параметр предыдущего месяца",
            "next_month: str | int - параметр следующего месяца",
            "calendar: dict - объект календаря с полем:",
            "  calendar.days: list[dict] - дни месяца, каждый с полями number, is_today, has_event",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    "pages/events/detail.html": {
        "description": (
            "Детальная страница события. Отображает информацию, "
            "тип, время, участников (если тип — встреча)."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "event: Event - объект события с полями id, name, type, description, start_datetime, end_datetime, team_name, created_at, meeting_participants (список с полями name, email) — заполняется при type == 'meeting'",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    # ────────────────────────────────────────────────
    #  Страницы — Встречи
    # ────────────────────────────────────────────────

    "pages/meetings/list.html": {
        "description": (
            "Страница списка встреч. Содержит карточки встреч, "
            "фильтр по команде и пагинацию."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "meetings: list[Meeting] - список встреч, каждая с полями id, name, description, start_datetime, end_datetime, team_name, location, participants (список с полем name)",
            "teams: list[Team] - список команд для фильтра (каждый с полями id, name)",
            "pagination: Pagination - объект пагинации с полями total_pages, current_page, has_previous, has_next, prev_page, next_page, pages",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },

    "pages/meetings/detail.html": {
        "description": (
            "Детальная страница встречи. Отображает информацию, "
            "повестку (agenda) и участников со статусами."
        ),
        "required_context": [
            "request: Request - контекст HTTP-запроса",
            "meeting: Meeting - объект встречи с полями id, name, description, start_datetime, end_datetime, team_name, location, agenda (список с полями title, description, presenter), participants (список с полями name, email, status)",
        ],
        "blocks": ["title", "head", "content"],
        "extends": "base.html",
    },
}
