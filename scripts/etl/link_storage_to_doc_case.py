#!/usr/bin/env python3
import json
import argparse
from sqlalchemy import select
from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.models import StorageObject, Document

def main():
    ap = argparse.ArgumentParser(description="Link storage_object to document/case by storage_ref")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    SessionLocal = get_sessionmaker()
    linked = 0
    with SessionLocal() as s:
        q = select(StorageObject)
        if args.limit:
            q = q.limit(args.limit)
        for so in s.scalars(q).all():
            # find document by storage_ref == so.key
            doc = s.scalars(select(Document).where(Document.storage_ref == so.key)).first()
            if not doc:
                continue
            changed = False
            if so.document_id != doc.id:
                if args.dry_run:
                    linked += 1
                    continue
                so.document_id = doc.id
                changed = True
            if so.case_pk != doc.case_pk:
                if args.dry_run:
                    linked += 1
                    continue
                so.case_pk = doc.case_pk
                changed = True
            if changed:
                linked += 1
        if not args.dry_run:
            s.commit()
    print(json.dumps({"linked": linked}))

if __name__ == "__main__":
    main()
