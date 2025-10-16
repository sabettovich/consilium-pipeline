# placeholder FastAPI entrypoint

from fastapi import FastAPI
from src.http_app.api.routers import documents
from src.http_app.api.routers import vault
from src.http_app.api.routers import problems


app = FastAPI(title="Consilium Pipeline API")
app.include_router(documents.router)
app.include_router(vault.router)
app.include_router(problems.router)
