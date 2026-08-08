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




# Встречи и события в виде календаря

async def claendar():
    ...

