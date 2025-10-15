from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.core.infrastructure.storage.s3_client import presign_post

router = APIRouter(prefix="/documents", tags=["documents"])


class PresignPutRequest(BaseModel):
    filename: str
    content_type: str
    size: int
    case_id: Optional[str] = None


class PresignPutResponse(BaseModel):
    url: str
    fields: dict
    expires_in: int


@router.post("/presign", response_model=PresignPutResponse)
def presign_put(payload: PresignPutRequest):
    if payload.size <= 0:
        raise HTTPException(status_code=400, detail="invalid size")
    try:
        resp = presign_post(payload.filename, payload.content_type, payload.size, expires_in=600)
        return PresignPutResponse(url=resp["url"], fields=resp["fields"], expires_in=600)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"presign error: {e}")
