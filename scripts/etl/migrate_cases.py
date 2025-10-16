#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Iterator

from sqlalchemy import select

from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.models import Tenant, Case

INP = Path("doc/etl/export/matters.jsonl")


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


def main():
    ap = argparse.ArgumentParser(description="Migrate matters to Case (idempotent upsert)")
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
            case_id = rec.get("matter_id")
            title = rec.get("client_name") or rec.get("folder_path") or case_id
            if not case_id:
                continue
            if args.dry_run:
                continue
            stmt = select(Case).where(Case.tenant_id == args.tenant, Case.case_id == case_id)
            row = s.scalars(stmt).first()
            if not row:
                s.add(Case(tenant_id=args.tenant, case_id=case_id, title=title))
                created += 1
            else:
                if (row.title or "") != (title or ""):
                    row.title = title
                    updated += 1
        if not args.dry_run:
            s.commit()
    print(json.dumps({"cases_created": created, "cases_updated": updated}))


if __name__ == "__main__":
    main()
