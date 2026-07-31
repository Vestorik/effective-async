| POST | `/auth/register` | guest | Регистрация |
| POST | `/auth/login` | guest | Токен |
| GET | `/users/me` | auth | Профиль |
| POST | `/teams` | manager | Создать команду |
| POST | `/teams/{id}/join` | auth | По invite_code |
| GET | `/teams/{id}/members` | member | Состав |
| CRUD | `/teams/{id}/tasks` | manager/member | Задачи |
| POST | `/tasks/{id}/comments` | member | Комментарий |
| POST | `/tasks/{id}/evaluation` | manager | Оценка |
| CRUD | `/teams/{id}/meetings` | manager | Встречи |
| GET | `/calendar` | auth | События за период |



# get для шаблона User или DetailUser

# post для логики UpdateUser

async def me():
    ...

# Отдельная страница /teams

async def teams_join():
    ...

async def teams_members():
    ...

async def teams_tasks():
    ...

async def tasks_comments():
    ...

async def tasks_evaluation():
    ...

async def teams_meetings():
    ...

# Встречи и события в виде календаря

async def claendar():
    ...


Задачи

Создать базавую страницу teams с использованием шаблонов teams + Projects + teams_user
Создать страницу Projects Projects + task + task_executor

Создать страницу calendar с отображением событий и встреч.

Создать rolechecker на основе декорации или миксина. 

Покрыть тестами не менее 80% кода