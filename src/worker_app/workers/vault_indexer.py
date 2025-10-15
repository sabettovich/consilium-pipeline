import os
import hashlib
import logging
from datetime import datetime
from typing import Optional, Tuple

import dramatiq
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.infrastructure.persistence.sqlalchemy.models import Artifact
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
                count += 1
            except Exception as e:
                log.warning("vault index error %s: %s", full, e)
    session.commit()
    log.info("vault indexed files=%s", count)
    return count


@dramatiq.actor(queue_name=HEALTH)
def index_vault_job() -> None:
    # This actor acts as a trigger; in a real run we'd create a session via factory/DI
    log.info("vault index job invoked (actor)")
