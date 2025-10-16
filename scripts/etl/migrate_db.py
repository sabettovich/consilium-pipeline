#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Iterator

from sqlalchemy import select

from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.models import StorageObject

DEF_IN = "doc/etl/export/storage_objects.jsonl"
REP = Path("doc/etl/etl_report.jsonl")


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


def main():
    ap = argparse.ArgumentParser(description="Migrate data into Postgres (idempotent upsert)")
    ap.add_argument("--in", dest="inp", default=DEF_IN, help="Input JSONL path (export)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    inp = Path(args.inp)
    if not inp.exists():
        print(json.dumps({"error": f"input not found: {inp}"}))
        sys.exit(2)

    SessionLocal = get_sessionmaker()
    upserts = 0
    with SessionLocal() as s:
        for rec in iter_jsonl(inp):
            bucket = rec.get("bucket") or os.getenv("S3_BUCKET")
            key = rec.get("key")
            size = rec.get("size")
            etag = rec.get("etag")
            tenant_id = rec.get("tenant_id") or "default"
            if not key:
                continue
            if args.dry_run:
                REP.parent.mkdir(parents=True, exist_ok=True)
                with REP.open("a", encoding="utf-8") as rf:
                    rf.write(json.dumps({"kind": "dry_upsert_storage_object", "bucket": bucket, "key": key}) + "\n")
                continue
            stmt = select(StorageObject).where(StorageObject.bucket == bucket, StorageObject.key == key)
            so = s.scalars(stmt).first()
            if not so:
                so = StorageObject(bucket=bucket, key=key, size=size, etag=etag, tenant_id=tenant_id)
                s.add(so)
            else:
                so.size = size or so.size
                so.etag = etag or so.etag
            upserts += 1
        s.commit()
    print(json.dumps({"upserts_storage_object": upserts}))


if __name__ == "__main__":
    main()
