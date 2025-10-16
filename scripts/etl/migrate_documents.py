#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import select

from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.models import Tenant, Case, Document

INP = Path("doc/etl/export/docs.jsonl")


def iter_jsonl(p: Path) -> Iterator[dict]:
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def ensure_tenant(s, tenant_id: str):
    row = s.get(Tenant, tenant_id)
    if not row:
        s.add(Tenant(tenant_id=tenant_id, name=tenant_id))
        s.flush()
    return tenant_id


def resolve_case_pk(s, tenant_id: str, case_id: Optional[str]) -> Optional[int]:
    if not case_id:
        return None
    stmt = select(Case).where(Case.tenant_id == tenant_id, Case.case_id == case_id)
    row = s.scalars(stmt).first()
    if row:
        return row.id
    return None


def main():
    ap = argparse.ArgumentParser(description="Migrate docs to Document (idempotent upsert)")
    ap.add_argument("--in", dest="inp", default=str(INP))
    ap.add_argument("--tenant", default=os.getenv("TENANT_ID", "default"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.inp)
    if not path.exists():
        print(json.dumps({"error": f"input not found: {path}"}))
        sys.exit(2)

    SessionLocal = get_sessionmaker()
    created = 0
    updated = 0
    with SessionLocal() as s:
        if not args.dry_run:
            ensure_tenant(s, args.tenant)
        for rec in iter_jsonl(path):
            doc_id = rec.get("doc_id")
            case_id = rec.get("matter_id")
            doc_kind = rec.get("class_name")
            title = rec.get("title")
            sha256 = rec.get("sha256_plain")
            status = rec.get("status")
            # origin_meta may contain fs info
            fs = None
            meta_raw = rec.get("origin_meta") or rec.get("fs")
            try:
                fs = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw) if meta_raw else None
            except Exception:
                fs = None
            fs = (fs or {}).get("fs") or fs or {}
            mime = fs.get("mime")
            size = fs.get("size")
            storage_ref = fs.get("key")
            if not doc_id:
                continue
            if args.dry_run:
                # just count would-be actions
                created += 1
                continue
            case_pk = resolve_case_pk(s, args.tenant, case_id)
            stmt = select(Document).where(Document.tenant_id == args.tenant, Document.idempotency_key == doc_id)
            row = s.scalars(stmt).first()
            if not row:
                row = Document(
                    tenant_id=args.tenant,
                    case_pk=case_pk,
                    doc_kind=doc_kind,
                    title=title,
                    mime=mime,
                    size=size,
                    sha256=sha256,
                    storage_ref=storage_ref,
                    idempotency_key=doc_id,
                    status=status,
                )
                s.add(row)
                created += 1
            else:
                # update basic fields if changed
                changed = False
                if row.case_pk != case_pk:
                    row.case_pk = case_pk; changed = True
                if (row.doc_kind or "") != (doc_kind or ""):
                    row.doc_kind = doc_kind; changed = True
                if (row.title or "") != (title or ""):
                    row.title = title; changed = True
                if (row.mime or "") != (mime or ""):
                    row.mime = mime; changed = True
                if (row.size or 0) != (size or row.size):
                    row.size = size or row.size; changed = True
                if (row.sha256 or "") != (sha256 or ""):
                    row.sha256 = sha256; changed = True
                if (row.storage_ref or "") != (storage_ref or ""):
                    row.storage_ref = storage_ref; changed = True
                if (row.status or "") != (status or ""):
                    row.status = status; changed = True
                if changed:
                    updated += 1
        if not args.dry_run:
            s.commit()
    print(json.dumps({"documents_created": created, "documents_updated": updated}))


if __name__ == "__main__":
    main()
