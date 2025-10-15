from __future__ import annotations

import logging
import urllib.parse
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.infrastructure.persistence.sqlalchemy.models import StorageObject
from src.core.infrastructure.messaging import queues
from src.worker_app.workers.ocr_pdf_small import ocr_pdf_small as w_ocr_pdf_small
from src.worker_app.workers.ocr_pdf_large import ocr_pdf_large as w_ocr_pdf_large
from src.worker_app.workers.ocr_img_small import ocr_img_small as w_ocr_img_small
from src.core.application.services.idempotency import InflightGuard


log = logging.getLogger(__name__)


def _ext_from_key(key: str) -> str:
    k = key.lower()
    if "." in k:
        return k.rsplit(".", 1)[-1]
    return ""


def _route(ext: str, size: int) -> str:
    if ext in ("jpg", "jpeg", "png"):
        return queues.OCR_IMG_SMALL
    if ext == "pdf":
        if size <= queues.SMALL_MAX_MB * 1024 * 1024:
            return queues.OCR_PDF_SMALL
        return queues.OCR_PDF_LARGE
    return queues.OCR_PDF_SMALL


def handle_s3_event(event: Dict[str, Any], db: Session) -> None:
    records = event.get("Records") or []
    guard = InflightGuard(ttl_seconds=600)
    for r in records:
        s3 = r.get("s3", {})
        bucket = s3.get("bucket", {}).get("name")
        obj = s3.get("object", {})
        raw_key = obj.get("key")
        if not bucket or not raw_key:
            continue
        key = urllib.parse.unquote_plus(raw_key)
        size = int(obj.get("size") or 0)
        etag = obj.get("eTag")

        stmt = select(StorageObject).where(StorageObject.bucket == bucket, StorageObject.key == key)
        so = db.scalars(stmt).first()
        if not so:
            so = StorageObject(bucket=bucket, key=key, size=size, etag=etag, tenant_id="default")
            db.add(so)
        else:
            so.size = size or so.size
            so.etag = etag or so.etag
        db.commit()

        # In-flight guard by S3 object identity to avoid duplicate concurrent enqueues
        lock_key = f"s3:{bucket}:{key}"
        if not guard.acquire(lock_key):
            log.info("skip duplicate in-flight enqueue for %s", lock_key)
            continue
        try:
            ext = _ext_from_key(key)
            q = _route(ext, size)
            if q == queues.OCR_IMG_SMALL:
                w_ocr_img_small.send(so.id)
            elif q == queues.OCR_PDF_SMALL:
                w_ocr_pdf_small.send(so.id)
            else:
                w_ocr_pdf_large.send(so.id)
            log.info("ingested s3 object bucket=%s key=%s size=%s -> queue=%s", bucket, key, size, q)
        finally:
            guard.release(lock_key)

