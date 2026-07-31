# Jinja2 шаблоны для Business Manage App

Набор Jinja2 шаблонов для FastAPI приложения управления бизнес-процессами.

## Структура шаблонов

```
app/src/api/templates/
├── base.html              # Базовый шаблон для всех HTML-страниц
├── api_docs.html          # Документация API
├── email/                 # Email-шаблоны
│   ├── notification.html  # Уведомления о задачах
│   ├── meeting.html       # Уведомления о встречах
│   └── event.html         # Уведомления о событиях
└── pages/                 # HTML-страницы приложения
    ├── index.html         # Главная страница
    ├── projects/          # Проекты
    │   ├── list.html      # Список проектов
    │   └── detail.html    # Детальная информация о проекте
    ├── teams/             # Команды
    │   ├── list.html      # Список команд
    │   └── detail.html    # Детальная информация о команде
    ├── tasks/             # Задачи
    │   ├── list.html      # Список задач
    │   └── detail.html    # Детальная информация о задаче
    ├── events/            # События
    │   ├── list.html      # Список событий
    │   └── detail.html    # Детальная информация о событии
    └── meetings/          # Встречи
        ├── list.html      # Список встреч
        └── detail.html    # Детальная информация о встрече
```

## Использование

### В FastAPI-эндпоинтах

```python
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="app/src/api/templates")

@app.get("/projects")
async def list_projects(request: Request):
    projects = [...]  # Получение данных из БД
    return templates.TemplateResponse(
        "pages/projects/list.html",
        {"request": request, "projects": projects}
    )
```

### В email-сервисах

```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("app/src/api/templates"))
template = env.get_template("email/notification.html")

html_content = template.render(
    user_name="Иван",
    task_name="Задача 1",
    notification_type="new_task",
    task_link="https://app.example.com/tasks/123"
)
```

## Особенности

- Все шаблоны написаны на русском языке
- Адаптивный дизайн (mobile-first)
- Использование CSS-переменных для легкой кастомизации
- Поддержка пагинации и фильтрации
- Email-шаблоны готовы к использованию с любыми email-провайдерами

## Технологии

- Jinja2 3.1.6+
- FastAPI 0.137.1+
- Python >=3.14

## Лицензия

© 2026 Business Manage App. Все права защищены.
