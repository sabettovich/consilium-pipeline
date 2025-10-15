# placeholder FastAPI entrypoint

from fastapi import FastAPI
from src.http_app.api.routers import documents


app = FastAPI(title="Consilium Pipeline API")
app.include_router(documents.router)
