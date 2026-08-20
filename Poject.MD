# Effect Mobile Lear — Business Management App

Высоконагруженное асинхронное веб-приложение для управления бизнес-процессами, командами и проектами. Разработано на стеке **Python 3.11+ / FastAPI** с соблюдением принципов чистой архитектуры (Clean Architecture) и разделения ответственности.

Приложение предоставляет **REST API** для внешних интеграций и **HTML-интерфейс** (SSR через Jinja2) для администрирования и работы пользователей.

---

## 🏗 Архитектура

Проект строго следует принципам SOLID, DRY и паттерну **Unit of Work (UoW)**. Слои изолированы и взаимодействуют только через четко определенные интерфейсы.

### Слои взаимодействия

`API Router → Handler (Controller) → Service (Domain Logic) → Repository (DAL) → Database`

1. **API Layer** (`app/src/api/client/api/`)
    * Определение эндпоинтов FastAPI.
    * Валидация входных данных через **Pydantic** модели.
    * Внедрение зависимостей (`Depends`) для получения сервисов и репозиториев.

2. **Handler Layer** (`app/src/api/handlers/`)
    * Контроллеры бизнес-логики.
    * Управление транзакциями через UoW и кэшированием.
    * Преобразование результатов сервисов в HTTP-ответы и обработка исключений.

3. **Service Layer** (`app/src/api/services/`)
    * Чистая бизнес-логика и правила домена.
    * Взаимодействие с интерфейсами репозиториев.
    * Не зависит от HTTP, БД или фреймворка.

4. **DAL (Data Access Layer)** (`app/src/api/dal/`)
    * **Models**: SQLAlchemy модели.
    * **Repositories**: Реализация паттерна Repository для работы с БД.
    * **UoW**: Управление транзакциями (обычное для записи, кэшированное для чтения).

5. **Base Infrastructure** (`app/src/base/`)
    * Централизованная конфигурация (Pydantic Settings).
    * Инициализация логирования и управление жизненным циклом приложения (`lifespan`).

---

## 🛠 Стек технологий

### Core

* **Язык**: Python >= 3.14
* **Web Framework**: FastAPI (0.137.1+)
* **Server**: Uvicorn (0.43.0+) с `uvloop` для максимальной производительности.

### Data & ORM

* **ORM**: SQLAlchemy (2.0.51+)
* **Drivers**: `asyncpg` (PostgreSQL Production), `aiosqlite` (Dev/Test)
* **Connection Pooling**: Асинхронные пулы соединений с `pool_pre_ping`.
* **Migrations**: Alembic (асинхронный контекст).

### Authentication & Security

* **JWT**: PyJWT с HTTP-only cookies (веб) и Bearer (API).
* **Password Hashing**: Passlib (Argon2id).
* **Validation**: Pydantic для строгой валидации всех входных данных.

### Infrastructure

* **Config**: `pydantic-settings` с загрузкой из `.env`.
* **Logging**: `concurrent-log-handler` (асинхронно-безопасный ротейтинг логов).
* **Caching**: Redis (интеграция через UoW для чтения).
* **Testing**: `pytest`, `pytest-asyncio`, `httpx`.

---

## 🚀 Ключевые возможности

### Управление данными

* **CRUD** для проектов, команд и пользователей.
* **Task Management**: Полная поддержка задач с приоритетами, оценками сложности, многопользовательским назначением и иерархией подзадач.
* **Кэширование**: Чтение из Redis с TTL для разгрузки базы данных.

### Безопасность (OWASP Top 10)

* **SQL-инъекции**: Исключены благодаря использованию ORM SQLAlchemy.
* **XSS**: Экранирование в шаблонах Jinja2.
* **CSRF**: Защита на уровне куки/сессии.
* **Rate Limiting**: Защита от перебора паролей.
* **Валидация**: Строгая проверка типов и значений на границе API.

### Производительность

* **Async/I/O**: Все внешние вызовы (БД, HTTP) асинхронны.
* **Connection Pooling**: Оптимизированные пулы соединений с настройками таймаутов.
* **Resource Management**: Автозакрытие соединений и чистка ресурсов через `lifespan`.

---

## ⚙️ Установка и запуск

### Требования

* Python >= 3.14
* PostgreSQL (Production) или SQLite (Dev)
* Redis (рекомендуется для кэширования)

### Шаги

1. **Клонирование и установка**

    ```bash
    git clone <url>
    cd buisenss-manage-app
    python -m venv venv
    source venv/bin/activate  # или venv\Scripts\activate на Windows
    pip install -r pyproject.toml  # или pip install -e .
    ```

1. Настройка окружения
    Создайте и заполните файл конфигурации в директории deploy:

    Bash
    cp deploy/.env.example deploy/.env  # Если файл .env.example существует

    Отредактируйте deploy/.env, указав реальные значения для секретов:

    ```INI

   # DB

        POSTGRES_HOST=localhost
        POSTGRES_PORT=5432
        POSTGRES_USER=effect_user
        POSTGRES_PASSWORD=<strong_password>
        POSTGRES_DB_NAME=effect_mobile_db

   # JWT

        _SECRET_KEY=<strong_random_key>

    ```

1. **Инициализация базы данных**

    ```bash
    # Запуск PostgreSQL через Docker
    docker compose -f deploy/docker-compose.yaml up postgres

    # Выполнение миграций
    alembic upgrade head
    ```

1. **Запуск приложения**

    ```bash
    python -m app.src.base.main
    ```

    *Или через Uvicorn напрямую:*

    ```bash
    uvicorn app.src.base.main:MAIN_APP --reload --host 0.0.0.0 --port 8000
    ```

### Дополнительные команды

* **Создание администратора**: `python app.manage --create-admin`
* **Создание фикстур**: `python app.manage --create-fixture`

---

## 📁 Структура директорий

```text
app/src/
├── api/
│   ├── client/
│   │   ├── api/          # FastAPI Routers (REST endpoints)
│   │   └── views/        # Jinja2 Templates (SSR views)
│   ├── handlers/         # Контроллеры (Handlers)
│   ├── services/         # Бизнес-логика (Services)
│
│
├── dal/              # Data Access Layer (ORM, Repos, UoW)
│
│
├── base/
│   ├── config.py         # Pydantic Settings (DB, Redis, Auth, Server)
│   ├── lifespan.py       # Startup/Shutdown логика
│   ├── main.py           # Точка входа (FastAPI app)
│   └── utils.py          # Утилиты валидации
└── manage.py             # CLI хелперы (админ, фикстуры)
