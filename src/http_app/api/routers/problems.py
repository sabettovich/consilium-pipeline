from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.repositories import ProblemLogRepository

router = APIRouter(prefix="/problems", tags=["problems"])


class ProblemLogItem(BaseModel):
    id: int
    tenant_id: str
    document_id: Optional[int] = None
    task_type: Optional[str] = None
    queue: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    recommendation: Optional[str] = None
    user_decision: Optional[str] = None
    decided_by: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProblemLogItem])
def list_problems(limit: int = 50):
    SessionLocal = get_sessionmaker()
    with SessionLocal() as s:
        repo = ProblemLogRepository(s)
        return repo.list(limit=limit)


class DecideRequest(BaseModel):
    decision: str
    decided_by: str


@router.post("/{pl_id}/decide", response_model=ProblemLogItem)
def decide_problem(pl_id: int, payload: DecideRequest):
    SessionLocal = get_sessionmaker()
    with SessionLocal() as s:
        repo = ProblemLogRepository(s)
        row = repo.decide(pl_id, payload.decision, payload.decided_by)
        if not row:
            raise HTTPException(status_code=404, detail="problem not found")
        return row
