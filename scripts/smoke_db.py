#!/usr/bin/env python3
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.models import Base, Tenant, Case, Document

DSN = "postgresql+psycopg2://consilium:consilium@localhost:55432/consilium"


def main():
    engine = create_engine(DSN, echo=False, future=True)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as s:
        # ensure tenant default
        tenant = s.get(Tenant, "default")
        if not tenant:
            tenant = Tenant(tenant_id="default", name="Default", created_at=datetime.utcnow())
            s.add(tenant)
            s.flush()
        # ensure case
        case = s.query(Case).filter(Case.tenant_id == tenant.tenant_id, Case.case_id == "2025-TEST-0001").one_or_none()
        if not case:
            case = Case(tenant_id=tenant.tenant_id, case_id="2025-TEST-0001", title="Smoke Case")
            s.add(case)
            s.flush()
        # document
        doc = Document(
            tenant_id=tenant.tenant_id,
            case_pk=case.id,
            doc_kind="intake",
            title="Smoke Doc",
            mime="text/plain",
            size=0,
            sha256=None,
            storage_ref=None,
            vault_path_main=None,
            idempotency_key="smoke-idem-1",
            status="registered",
            created_at=datetime.utcnow(),
        )
        s.add(doc)
        s.commit()
        print({
            "tenant_id": tenant.tenant_id,
            "case_id": case.case_id,
            "document_id": doc.id,
        })


if __name__ == "__main__":
    main()
