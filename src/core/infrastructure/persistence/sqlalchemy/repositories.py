from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Document


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get_by_idempotency(self, tenant_id: str, idempotency_key: str) -> Optional[Document]:
        stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.idempotency_key == idempotency_key,
        )
        return self.s.scalars(stmt).first()

    def upsert_by_idempotency(
        self,
        *,
        tenant_id: str,
        case_pk: int,
        idempotency_key: str,
        doc_kind: Optional[str] = None,
        title: Optional[str] = None,
        mime: Optional[str] = None,
        size: Optional[int] = None,
        sha256: Optional[str] = None,
        storage_ref: Optional[str] = None,
        vault_path_main: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Document:
        existing = self.get_by_idempotency(tenant_id, idempotency_key)
        if existing:
            # Update non-null fields
            if doc_kind is not None:
                existing.doc_kind = doc_kind
            if title is not None:
                existing.title = title
            if mime is not None:
                existing.mime = mime
            if size is not None:
                existing.size = size
            if sha256 is not None:
                existing.sha256 = sha256
            if storage_ref is not None:
                existing.storage_ref = storage_ref
            if vault_path_main is not None:
                existing.vault_path_main = vault_path_main
            if status is not None:
                existing.status = status
            self.s.flush()
            return existing

        doc = Document(
            tenant_id=tenant_id,
            case_pk=case_pk,
            idempotency_key=idempotency_key,
            doc_kind=doc_kind,
            title=title,
            mime=mime,
            size=size,
            sha256=sha256,
            storage_ref=storage_ref,
            vault_path_main=vault_path_main,
            status=status or "registered",
        )
        self.s.add(doc)
        self.s.flush()
        return doc

