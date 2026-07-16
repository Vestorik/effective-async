# Data Access Layer (DAL)

**Назначение**: Модуль `app.src.dal` отвечает за абстракцию слоя доступа к данным, изолируя бизнес-логику от инфраструктурных деталей (ORM, БД, кэш). Реализует архитектуру Clean Architecture и паттерны DDD.

---

## 📦 Состав

| Компонент | Назначение |

| `database/` | ORM-модели, движок, сессии и управление транзакциями |
| `cache/` | Кэширование данных через Redis (RedisConfig, CacheManager, CachedUnitOfWork) |
| `migrations/` | Alembic-конфигурация и генерируемые миграции |
| `main.py` | Централизованный интерфейс `DataManager` для сервисов |

---

## 🏗️ Архитектура

API layer
↓
Services (business logic)
↓
DAL
├── database/       → ORM, движок, репозитории, UnitOfWork
├── cache/          → Redis, кэширование (TypedProxy + TTL)
└── migrations/     → Alembic (автоматические миграции с autogenerate)

### ✅ Принципы

- **SOLID**: Single Responsibility (каждый репозиторий — одна модель), Dependency Inversion (абстрактный `BaseRepository`).
- **Composition over Inheritance**: Прокси-обёртки (CachedRepositoryProxy) используют композицию.
- **DRY**: Универсальные CRUD-операции вынесены в `BaseRepository`.
- **KISS**: Простой интерфейс без избыточной абстракции.
- **Twelve-Factor App**: Конфигурация через переменные окружения (`POSTGRES_*`, `REDIS_*`).

---

## 🔧 Технологии

| Технология | Использование |

| **SQLAlchemy 2.x (async)** | ORM с `async_sessionmaker`, `AsyncEngine`. |
| **asyncpg** | Основной драйвер PostgreSQL. |
| **aiosqlite** | Fallback-движок (для dev/test, отключается в prod через `SQLITE_SUPPORTED = False`). |
| **Alembic** | Управление миграциями (асинхронный контекст, `target_metadata = BaseModel.metadata`). |
| **Redis** | Кэширование GET-операций (TTL, инвалидация через `clear_pattern`). |
| **tenacity** | Retry-логика (`session_transaction()` с экспоненциальной задержкой). |

---

## 🗂️ Структура папок и файлов

app/src/dal/
├── main.py                      # Централизованный интерфейс (DataManager)
├── dal.md                       # Этот файл
├── database/
│   ├── models.py                # ORM-модели (UserModel, TeamModel и др.)
│   ├── engine.py                # Движок, конфигурация (PostgresDatabaseConfig, start_engine)
│   ├── repositories.py          # Репозитории (UserRepository, ProjectRepository и др.)
│   └── session_manage.py        # UnitOfWork, session_transaction(), DataBaseManager
├── cache/
│   └── cache_manager.py         # RedisConfig, CacheManager, CachedUnitOfWork
└── migrations/
├── alembic.ini              # Настройки Alembic
├── env.py                   # Асинхронный контекст выполнения миграций
└── script.py.mako           # Шаблон миграций

## 🚀 Типичное использование

```python
# 1. Инициализация и получение менеджера
from app.src.dal.main import get_data_manager

manager = await get_data_manager()

# 2. Работа с БД без кэша
async with manager() as uow:
    user = await uow.users.get_by_email("alex@example.com")
    if not user.check_password("secret"):
        raise InvalidCredentials()
    user.email = "new@example.com"
    await uow.users.update(user)

# 3. Работа с кэшированием
async with manager.cache(timedelta(minutes=10)) as cuow:
    projects = await cuow.projects.get_all()  # Кэшируется
    await cuow.projects.update(project)       # Обходит кэш 

```

## ⚙️ Миграции

Bash

### Создание новой миграции

cd app/src/dal/migrations
alembic revision --autogenerate -m "add task priority"

### Применение миграций

alembic upgrade head

### Откат к предыдущей версии

alembic downgrade -1

## 🛡️ Безопасность

- SQL-инъекции: Исключены через ORM (параметризованные запросы).
- Хэширование паролей: bcrypt через passlib.
- Логирование: Пароли, токены, персональные данные не логируются.
- Валидация: Все входные данные валидируются Pydantic-моделями.
🔧 Технические детали реализации
🔹 Управление транзакциями
Механизм Описание
UnitOfWork Реализует паттерн Unit of Work (DDD). Объединяет все репозитории в одной сессии, гарантирует атомарность через commit()/rollback(). Применяется в HTTP-запросах и сервисах.
session_transaction() Контекстный менеджер с retry-логикой через tenacity. При OperationalError создаёт новую сессию, откатывая все изменения предыдущей попытки. Подходит для фоновых задач и cron-的工作.
DataBaseManager Централизованный фасад для DI: хранит engine и session_maker, предоставляет uow() для создания новых единиц работы.

## ⚠️ Рекомендация

HTTP-запросы — только UnitOfWork.
Фоновые задачи — session_transaction() (если допустимо повторение без состояния).
Данные в session_transaction() не сохраняются между retry.

## 🔹 Стратегия кэширования

Элемент Поведение
CachedRepositoryProxy Перехватывает вызовы методов репозитория. Кэширует только результаты методов, возвращающие данные (get_by_id, get_all, get_all_paginated). Write-операции (create, update, delete) обходят кэш.
CachedUnitOfWork Интегрирует кэширование на уровне UnitOfWork. Автоматически оборачивает репозитории в CachedRepositoryProxy.
CacheManager Низкоуровневый интерфейс Redis: get(), setex(), delete(), clear_pattern(). Не обрабатывает ошибки — только логирует через logger.error().

## 📝 Формат ключа кэша

"{prefix}:{method}:{arg1}:{arg2}:kw1={val1}"

Пример: "users:get_by_email:alex@example.com"

arg и kwarg сериализуются через repr() для уникальности.
None и пустые строки сохраняются как "None" и "".

🛑 Важно:

Кэш не инвалидируется автоматически. Для update()/delete() используйте clear_pattern("users:*").
Не кэшируйте данные с высокой частотой обновления (рисик устаревания).

## 🔹 Оптимизация ORM-запросов

Техника Применение Эффект
selectinload() Для загрузки связанных коллекций (task.executors) Избегает N+1 запросов
joinedload() Для загрузки связанных объектов (user.team) Единый LEFT JOIN запрос
.unique() После joinedload() с M:N связями Удаляет дубликаты из результата
func.count() В get_all_paginated() Точная пагинация (но медленно на больших таблицах)

## 🔹 Обработка ошибок

Уровень Обработка
Redis При ConnectionError/TimeoutError логируется предупреждение, операция возвращает None/0.
БД Ошибки SQLAlchemy (IntegrityError, OperationalError) пропускаются через ORM. Логируются только имена классов (без данных).
Пароли/токены Логируются как "[REDACTED]". Никаких %s, %r — только logger.error("%s", "Message").

## 🔐 Безопасность

Пароли, токены, email — не логируются.
OperationalError логируется как logger.warning("OperationalError: %s", type(ex).**name**).

## 📦 Зависимости и окружение

🔹 Обязательные пакеты (production)
Пакет Версия Назначение
sqlalchemy[asyncio] >=2.0.48 ORM с поддержкой asyncio.
asyncpg >=0.31.0 Драйвер PostgreSQL (быстрее aiopg).
alembic >=1.13.1 Миграции БД (асинхронный контекст).
redis >=5.0.1 Кэширование через Redis.
tenacity >=9.1.4 Retry-логика.
passlib[bcrypt] >=1.7.4 Хэширование паролей.
pydantic-settings >=2.5.2 Конфигурация через .env.
fastapi >=0.115.0 Веб-фреймворк (для main.py).
uvicorn >=0.34.0 ASGI-сервер.
🔹 Вспомогательные (dev/test)
Пакет Версия Назначение
aiosqlite >=0.22.0 Fallback-движок SQLite для dev/test.
pytest >=8.0.0 Unit-тесты.
pytest-asyncio >=0.24.0 Асинхронные тесты.
pytest-mock >=3.14.0 Моки Redis/ORM.
httpx >=0.28.0 Интеграционные тесты через TestClient.

📦 Зависимости и окружение
🔹 Рекомендуемая конфигурация .env
ENV

## PostgreSQL

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=app_user
POSTGRES_PASSWORD=secure_pass
POSTGRES_DB=app_db
POSTGRES_POOL_SIZE=15
POSTGRES_POOL_PRE_PING=true
POSTGRES_POOL_RECYCLE=3600

## Redis

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

🔹 Миграция

```Bash
cd app/src/dal/migrations
alembic revision --autogenerate -m "add user avatar"
alembic upgrade head
```

✅ Ключевые принципы:

Чистота: DAL не зависит от HTTP/WS/CLI.
Надёжность: Retry, таймауты, валидация.
Простота: Минимальная абстракция, понятные имена.
Масштабируемость: Redis, пулы, миграции.
