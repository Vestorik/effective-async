from fastapi import APIRouter
from fastapi.templating import Jinja2Templates


prefix = "/views"
templates = Jinja2Templates(directory="app/templates")
