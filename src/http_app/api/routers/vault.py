from fastapi import APIRouter
from src.worker_app.workers.vault_indexer import index_vault_job

router = APIRouter(prefix="/vault", tags=["vault"])


@router.post("/index")
def trigger_index():
    index_vault_job.send()
    return {"status": "queued"}
