# Описание

## Настройка перед запуском

1. Установите виртуальное окружение

2. Заполните .env секреты
3. Запустите базу данных
    - docker compose -f deploy/docker-compose.yaml up postgres

4. Проведите миграцию базы данных alembic
    - alembic revision -m "add table"
    - alembic upgrade head

5. Запустите приложение
    - python -m app.src.base.main

6. Для создания фикстур используйте
    - app.manage --create-fixture

7. Для создания администратора используйте
    - app.manage --create-admin

Или воспользуётесь командой - docker compose -f deploy/docker-compose.yaml up и соберите dockerfile

## Описание Проекта

Проект посторен на слоевой архитектуре
dal - api

Модуль dal представляет собой  инструмент для работы с базой данных и кеширование. Позволяет оуществлять запросы к объявлённым моделям.
model - repository - data_base_manager(UOW) - data_manager
cache - cache_manager(UOW) ----------------------|

Методы моделей реализованы в repository доступ к которым осушествляется через data_base_manager с помощью паттерна UnitOfWork
Кэширование реализованно аналогично работе с моделями и предостовляет теже методы репозиториев, но дайт возможность обратится в кэш или записать туда информацию из БД
Для унификации доступа к работе с БД создан data_manager который предоставляет одну точку для использования data_base_manager и cache_manager

Модуль api реализует бищнес логику и работает методами репозитория.
services(pydantic_schems) - handlers - api
                                |---- views

Эндпоинты разделен на api и views.
При появлении views повилась потребность в переиспользовании логики, поэтому она была вынесина в handlers.
В api и views предпологалось использовать только для получения отдачи запроса в нужно формате, но на данный момент раздеоение осуществленно только для api

handlers реализуют работу, получают data_manager из Dependce api, определяют UOW и вызывают методы services
services получают данные из БД с помощью экземпляра репозитория переданного из handlers
Для валидации данных используются схемы pydantic

## Тестирование

pytest \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=html:htmlcov \
  -v
