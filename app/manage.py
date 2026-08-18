from datetime import timezone, datetime
import argparse
import asyncio

from app.src.api.services.auth import RoleType
from app.src.dal.database.models import (
    CommentModel,
    EventModel,
    MeetingModel,
    ProjectModel,
    TaskExecutorModel,
    TaskModel,
    TeamModel,
    UserModel,
    pwd_context,
)
from app.src.dal.main import get_data_manager


async def create_admin():
    try:
        name = input("Введите своё имя\nName: ")
        email = input('Введите Email, Обязательное поле, исрользуется для аутентификации\nEmail: ')
        password = input('Введите пароль, Обязательное поле, исрользуется для аутентификации\nPassword: ')
            
        
        admin_model = UserModel(
        username = name,
        email=email,
        role=RoleType.ADMIN.value,
        hashed_password=pwd_context.hash(password)
        )
        
        data_manager = await get_data_manager()
        async with data_manager() as uow:
            await uow.users.create(admin_model)
        print(f"Администратор {name} успешно создан")
    except Exception as e:
        print("Что-то пошло не так\n", e)
    
async def create_fixtures():
    """
    Создаёт полный набор тестовых данных для всех моделей.
    
    Генерирует данные с использованием циклов и именованных переменных (test_user_num, test_team_num и т.д.).
    """
    try:
        print("Создание тестовых данных...")
        data_manager = await get_data_manager()
        
        # Используем контекстный менеджер для работы с БД
        async with data_manager() as uow:
            # 1. Создаем пользователей
            users = []
            for i in range(1, 4): # Создаем 3 тестовых пользователя
                user = UserModel(
                    username=f"test_user_{i}",
                    email=f"test_user_{i}@example.com",
                    role=RoleType.USER.value,
                    hashed_password=pwd_context.hash("password123")
                )
                users.append(user)
                await uow.users.create(user)
            
            # 2. Создаем команды
            teams = []
            for i in range(1, 3): # Создаем 2 команды
                team = TeamModel(name=f"test_team_{i}")
                teams.append(team)
                await uow.teams.create(team)
            
            # 3. Назначаем пользователей в команды (1:N)
            for i, user in enumerate(users):
                user.team_id = teams[i % len(teams)].id # Распределяем по циклу  # ty: ignore[invalid-assignment]
                await uow.users.update(user) # Обновляем пользователя с привязкой к команде

            # 4. Создаем проекты
            projects = []
            for i in range(1, 3):
                project = ProjectModel(
                    name=f"test_project_{i}",
                    description=f"Описание тестового проекта {i}"
                )
                projects.append(project)
                await uow.projects.create(project)

            # 5. Создаем задачи
            tasks = []
            for i in range(1, 4):
                task = TaskModel(
                    name=f"test_task_{i}",
                    description=f"Задача номер {i}",
                    project_id=projects[i % len(projects)].id, # Привязка к проекту
                    estimate=10
                )
                tasks.append(task)
                await uow.tasks.create(task)

            # 6. Создаем исполнителей задач (M:N через TaskExecutorModel)
            for i, task in enumerate(tasks):
                # Назначаем первого пользователя на каждую задачу для теста
                if users:
                    executor = TaskExecutorModel(
                        user_id=users[0].id,
                        task_id=task.id,
                        estimate=5
                    )
                    await uow.task_executors.create(executor)

            # 7. Создаем комментарии
            if tasks and users:
                comment = CommentModel(
                    description="Тестовый комментарий",
                    author_id=users[0].id,
                    task_id=tasks[0].id
                )
                await uow.comments.create(comment)

            # 8. Создаем встречи (Meeting)
            if teams:
                meeting = MeetingModel(
                    name="test_meeting",
                    description="Тестовая встреча",
                    start_datetime=datetime.now(timezone.utc),
                    end_datetime=datetime.now(timezone.utc)
                )
                # Встреча может быть связана с командами через посредническую таблицу
                # Примечание: Убедитесь, что у вас есть метод создания встреч в репозитории,
                # поддерживающий связь с командами, либо свяжите их после создания
                await uow.meetings.create(meeting)

            # 9. Создаем события (Event)
            event = EventModel(
                name="test_event",
                description="Тестовое событие",
                start_datetime=datetime.now(timezone.utc),
                end_datetime=datetime.now(timezone.utc)
            )
            await uow.events.create(event)
            
            # Фиксация транзакции происходит автоматически при выходе из контекста,
            # если нет явного отката.

        print("Тестовые данные успешно созданы.")
        
    except Exception as e:
        print(f"Ошибка при создании тестовых данных: {e}")
        raise
    

async def main():
    """
    Основной punto входа для управления приложением.
    """
    parser = argparse.ArgumentParser(description="Управление приложением")
    # Добавляем аргумент create_admin
    parser.add_argument(
        "--create-admin",
        action="store_true",
        help="Создать административного пользователя"
    )
    
    parser.add_argument(
        "--create-fixtures",
        action="store_true",
        help="Создать тестовые данные (fixtures)"
    )
    
    args = parser.parse_args()

    if args.create_admin:
        await create_admin()
    elif args.create_fixtures:
        await create_fixtures()
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())