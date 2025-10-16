import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Optional, Tuple

import dramatiq
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.infrastructure.persistence.sqlalchemy.models import Artifact, StorageObject
from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.storage.paths import vault_root
from src.core.infrastructure.messaging.queues import HEALTH

log = logging.getLogger(__name__)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _try_parse_main_md(path: str) -> Optional[Tuple[str, str, int]]:
    # .../tenant/{tenant_id}/case/{case_id}/docs/{document_id}.md
    parts = os.path.normpath(path).split(os.sep)
    try:
        idx = parts.index("tenant")
        tenant_id = parts[idx + 1]
        if parts[idx + 2] != "case":
            return None
        case_id = parts[idx + 3]
        if parts[idx + 4] != "docs":
            return None
        doc_filename = parts[idx + 5]
        if not doc_filename.endswith(".md"):
            return None
        document_id = int(os.path.splitext(doc_filename)[0])
        return tenant_id, case_id, document_id
    except Exception:
        return None


def _upsert_artifact(s: Session, tenant_id: str, document_id: int, path: str, sha256: str, size: int) -> None:
    stmt = select(Artifact).where(
        Artifact.tenant_id == tenant_id,
        Artifact.document_id == document_id,
        Artifact.vault_path == path,
    )
    row = s.scalars(stmt).first()
    if row:
        row.sha256 = sha256
        row.size = size
        row.updated_at = datetime.utcnow()
        s.flush()
        return
    art = Artifact(
        tenant_id=tenant_id,
        document_id=document_id,
        kind="vault_md",
        vault_path=path,
        sha256=sha256,
        size=size,
        metrics=None,
    )
    s.add(art)
    s.flush()


def index_vault_once(session: Session, base: Optional[str] = None) -> int:
    base_dir = base or vault_root()
    count = 0
    # prepare report file
    os.makedirs("logs", exist_ok=True)
    report_path = os.path.join("logs", "vault_index.jsonl")
    summary = {"processed": 0, "updated": 0, "errors": 0, "ts": datetime.utcnow().isoformat()}
    for root, _dirs, files in os.walk(base_dir):
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            full = os.path.join(root, fn)
            meta = _try_parse_main_md(full)
            if not meta:
                continue
            tenant_id, case_id, document_id = meta
            try:
                sha = _sha256_file(full)
                size = os.path.getsize(full)
                _upsert_artifact(session, tenant_id, document_id, full, sha, size)
                with open(report_path, "a", encoding="utf-8") as rf:
                    rf.write(json.dumps({
                        "tenant_id": tenant_id,
                        "case_id": case_id,
                        "document_id": document_id,
                        "path": full,
                        "sha256": sha,
                        "size": size,
                        "ts": datetime.utcnow().isoformat(),
                        "event": "indexed"
                    }) + "\n")
                count += 1
                summary["processed"] += 1
                summary["updated"] += 1
            except Exception as e:
                summary["errors"] += 1
                log.warning("vault index error %s: %s", full, e)
    session.commit()
    log.info("vault indexed files=%s, updated=%s, errors=%s", summary["processed"], summary["updated"], summary["errors"])
    # write summary entry
    with open(report_path, "a", encoding="utf-8") as rf:
        rf.write(json.dumps({"summary": summary}) + "\n")
    return count


@dramatiq.actor(queue_name=HEALTH)
def index_vault_job() -> None:
    log.info("vault index job invoked (actor)")
    SessionLocal = get_sessionmaker()
    with SessionLocal() as s:
        index_vault_once(s)


def _iter_vault_main_md(base: str):
    for root, _dirs, files in os.walk(base):
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            full = os.path.join(root, fn)
            meta = _try_parse_main_md(full)
            if not meta:
                continue
            yield full, meta


def report_diffs(session: Session, base: Optional[str] = None) -> None:
    os.makedirs("logs", exist_ok=True)
    diff_path = os.path.join("logs", "vault_diff.jsonl")
    # truncate on start if requested
    if os.getenv("VAULT_DIFF_TRUNCATE_ON_START", "0") in ("1", "true", "TRUE", "yes"):
        with open(diff_path, "w", encoding="utf-8"):
            pass
    base_dir = base or vault_root()
    written = 0
    # Vault vs Artifact
    for full, (tenant_id, case_id, document_id) in _iter_vault_main_md(base_dir):
        try:
            sha = _sha256_file(full)
            size = os.path.getsize(full)
        except Exception as e:
            with open(diff_path, "a", encoding="utf-8") as rf:
                rf.write(json.dumps({
                    "kind": "error_read_vault",
                    "path": full,
                    "error": str(e),
                }) + "\n")
            continue
        stmt = select(Artifact).where(
            Artifact.tenant_id == tenant_id,
            Artifact.document_id == document_id,
            Artifact.vault_path == full,
        )
        row = session.scalars(stmt).first()
        if not row:
            with open(diff_path, "a", encoding="utf-8") as rf:
                rf.write(json.dumps({
                    "kind": "missing_artifact",
                    "tenant_id": tenant_id,
                    "case_id": case_id,
                    "document_id": document_id,
                    "path": full,
                }) + "\n")
                written += 1
        else:
            if (row.sha256 != sha) or (row.size != size):
                with open(diff_path, "a", encoding="utf-8") as rf:
                    rf.write(json.dumps({
                        "kind": "mismatch_artifact",
                        "tenant_id": tenant_id,
                        "case_id": case_id,
                        "document_id": document_id,
                        "path": full,
                        "db_sha256": row.sha256,
                        "file_sha256": sha,
                        "db_size": row.size,
                        "file_size": size,
                    }) + "\n")
                    written += 1

    # Optional: S3 vs StorageObject
    try:
        from src.core.infrastructure.storage.s3_client import create_s3_client
        import os as _os
        bucket = _os.getenv("S3_BUCKET")
        if bucket:
            s3 = create_s3_client()
            stmt = select(StorageObject).limit(100)
            for so in session.scalars(stmt).all():
                try:
                    head = s3.head_object(Bucket=so.bucket or bucket, Key=so.key)
                    s3_size = int(head.get("ContentLength", 0))
                    s3_etag = head.get("ETag", "").strip('"')
                    mism = (so.size is not None and so.size != s3_size) or (so.etag and so.etag != s3_etag)
                    if mism:
                        with open(diff_path, "a", encoding="utf-8") as rf:
                            rf.write(json.dumps({
                                "kind": "mismatch_s3",
                                "bucket": so.bucket,
                                "key": so.key,
                                "db_size": so.size,
                                "s3_size": s3_size,
                                "db_etag": so.etag,
                                "s3_etag": s3_etag,
                            }) + "\n")
                            written += 1
                except Exception as e:
                    with open(diff_path, "a", encoding="utf-8") as rf:
                        rf.write(json.dumps({
                            "kind": "error_s3_head",
                            "bucket": so.bucket,
                            "key": so.key,
                            "error": str(e),
                        }) + "\n")
                        written += 1
    except Exception as e:
        with open(diff_path, "a", encoding="utf-8") as rf:
            rf.write(json.dumps({"kind": "error_init_s3", "error": str(e)}) + "\n")

    log.info("vault diff written entries=%s", written)


@dramatiq.actor(queue_name=HEALTH)
def vault_diff_job() -> None:
    log.info("vault diff job invoked (actor)")
    SessionLocal = get_sessionmaker()
    with SessionLocal() as s:
        report_diffs(s)
