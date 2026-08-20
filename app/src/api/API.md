# Effect Mobile Lear — Business Management App

Высоконагруженное асинхронное веб-приложение для управления бизнес-процессами, командами и проектами. Разработано на стеке **Python 3.11+ / FastAPI**.

Предоставляет **REST API** для интеграций и **HTML-интерфейс** (SSR через Jinja2) для администрирования и работы пользователей.

---

## 📂 Архитектура

Проект строго следует принципам чистой архитектуры и разделения ответственности (Separation of Concerns).

### Структура модулей

Слои взаимодействия: `API → Handler → Service → Repository → Database`

1. **API Layer** (`app/src/api/client/api/`)
    * Определения эндпоинтов FastAPI.
    * Валидация входных данных через Pydantic-схемы.
    * Использование `DependsDataManager` для внедрения зависимостей.

2. **Handler Layer** (`app/src/api/handlers/`)
    * Контроллеры бизнес-логики.
    * Управление Unit of Work (UoW) и кэшированием.
    * Преобразование результатов сервисов в HTTP-ответы и обработка исключений.

3. **Service Layer** (`app/src/api/services/`)
    * Чистая бизнес-логика и правила домена.
    * Взаимодействие с интерфейсами репозиториев.
    * Не зависит от HTTP, БД или фреймворка.

4. **DAL (Data Access Layer)** (`app/src/api/dal/`)
    * **Models**: SQLAlchemy модели.
    * **Repositories**: Реализация паттерна Repository для работы с БД.
    * **UoW**: Управление транзакциями и сессиями (обычное для записи, кэшированное для чтения).

5. **Common**
    * `shems.py`: Pydantic модели (DTO) для сериализации/валидации.
    * `exceptions.py`: Пользовательские исключения (UserNotFound, InvalidCredentials и др.).
    * `admin/`: Конфигурация SQLAdmin панели.
    * `client/views/`: HTML-шаблоны (Jinja2) для SSR.

---

## 🛠 Стек технологий

### Core

* **Язык**: Python 3.11+
* **Web Framework**: FastAPI (0.137.1)
* **Server**: Uvicorn (0.43.0+)

### Data & ORM

* **ORM**: SQLAlchemy (2.0.48+)
* **Drivers**: `asyncpg` (PostgreSQL), `aiosqlite` (Dev/Test)
* **Connection Pooling**: Асинхронные пулы соединений

### Authentication & Security

* **JWT**: PyJWT (2.12.1+)
* **Password Hashing**: Passlib (Argon2id)
* **Protection**: CSRF, XSS, Rate Limiting

### Infrastructure & DevOps

* **Config**: python-dotenv
* **Logging**: concurrent-log-handler
* **Testing**: pytest, pytest-asyncio, httpx
* **Deployment**: Docker, docker-compose

---

## 🚀 Ключевые возможности

### Аутентификация и Пользователи

* Регистрация, вход/выход.
* Безопасное хранение паролей (Argon2).
* JWT-токены: HTTP-only cookies (для браузера) и Bearer (для API).
* Ролевая модель: Admin, Manager, User.

### Управление командами и проектами

* CRUD операции для команд и проектов.
* Назначение менеджеров и участников.
* Вложенная структура проектов.

### Task Management

* Полный цикл задач: создание, статусы, приоритеты (Low, Medium, High).
* Назначение исполнителей (Multi-assignment).
* Оценка сложности (Estimates).
* Иерархическая структура подзадач.

### Производительность

* Кэширование данных чтения (TTL) через Cache Unit of Work.
* Асинхронная I/O обработка.

---

## 📂 Структура директорий

```text
app/src/api/
├── main.py              # Точка входа, сборка роутеров, инициализация
├── shems.py             # Pydantic-схемы (DTO)
├── exceptions.py        # Кастомные исключения
├── client/
│   ├── api/             # REST API эндпоинты (Routes)
│   └── views/           # HTML-шаблоны (Jinja2) и SSR логика
├── handlers/            # Контроллеры (Handlers)
├── services/            # Бизнес-логика (Services)
│   ├── base_services.py # Базовые CRUD-операции
│   └── ...              # Сервисы домена
├── dal/                 # Data Access Layer
│   ├── database/
│   │   ├── models.py    # SQLAlchemy модели
│   │   └── repositories.py
│   └── main.py          # DataManager и UoW
└── admin/               # SQLAdmin конфигурация
⚙️ Установка и запуск
Требования
Python >= 3.11
PostgreSQL (Production) или SQLite (Dev)
Шаги

Клонирование и установка зависимостей


Bash
git clone <url>
cd buisenss-manage-app
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt


Настройка окружения


Bash
cp .env.example .env

Заполните переменные в .env:


DATABASE_URL: URL подключения (напр. sqlite+aiosqlite:///./app.db или postgresql+asyncpg://...)
SECRET_KEY: Ключ для подписи JWT
DEBUG: True для отладки


Запуск


Bash
uvicorn app.src.api.main:app --reload --host 0.0.0.0 --port 8000

Доступ
API Docs: http://localhost:8000/docs
Admin Panel: http://localhost:8000/admin
Dashboard: http://localhost:8000/views/dashboard
🧪 Тестирование
Используются юнит-тесты для сервисов и интеграционные тесты для API.
Тесты изолированы, используют транзакции с откатом (rollback) или in-memory базу данных.

Bash
# Установка зависимостей для тестов
pip install pytest pytest-asyncio httpx

# Запуск
pytest
🔒 Безопасность
Пароли: Хэширование через Argon2id.
Токены: JWT через HTTP-only куки (веб) или Authorization header (API). Передача только по HTTPS.
Валидация: Строгая валидация входных данных через Pydantic-модели.
Защита:
SQL-инъекции: Параметризованные запросы через ORM/AsyncPg.
XSS: Экранирование в Jinja2.
CSRF: Защита на уровне куки/сессии.
Rate Limiting: Защита от перебора паролей.
