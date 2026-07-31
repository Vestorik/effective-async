from fastapi import APIRouter
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/src/api/templates")


index_views_router =  APIRouter()

