@event_router.post(
    "",
    response_model=EventSheme,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новое событие",
    description="Создаёт событие (дедлайн, напоминание). Валидирует start_datetime < end_datetime.",
    responses={
        201: {"description": "Событие успешно создано"},
        400: {"description": "Некорректные временные интервалы"},
        404: {"description": "Пользователь не найден"},
    },
)
async def create_event_api(
    event_data: Annotated[EventCreate, ...],
    user_id: UUID,
    data_manager: DependsDataManager,
):
    data = await create_event(event_data, user_id, data_manager)
    return HTMLResponse(template.render(**data)) 