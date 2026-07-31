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


Смотри - на одной странице будут проекты и комманды. 
В левой части команды в правой проекты. 
у проекта список задач и комманд, задачи имеют подсписок исполнителей.
Вот пример того, как можно организовать
/projects
team1   5 members     |project_name             |project_name2
team2   3 members     |team1, team2 ...         |team3, team2 ...     
                      |                         | ...
...                   |task1      2 executors
...                   |task2      3 executors
...                   |task3      1 2executors
...                   | ...
Для get нам понадобится вернуть список всех команд, количество членов каждой команды, все проекты и задачи.Смотри - на одной странице будут проекты и комманды. В левой части команды в правой проекты. у проекта список задач и комманд, задачи имеют подсписок исполнителей. Можно будет добавить проект, задачу, создать комманду и добавить в неё членов, при нажатии на задачу будем открывать окно с детальным описанием задачи и её исполнителями где можно будет добавить комментарии и поставть оценку исполнителя. Для get нам понадобится вернуть список всех команд, проектов и задач. 
Можем создавать команды, задачи, проекты и изменять их
При нажатии на команду или задачу будем открывать их detail в котором можно их изменять 

