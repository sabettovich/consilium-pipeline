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

INP = Path("doc/etl/export/docs.jsonl")
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


def log(entry: dict):
    REP.parent.mkdir(parents=True, exist_ok=True)
    with REP.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Upsert storage_object from docs export (fs info)")
    ap.add_argument("--in", dest="inp", default=str(INP))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.inp)
    if not path.exists():
        print(json.dumps({"error": f"input not found: {path}"}))
        sys.exit(2)

    SessionLocal = get_sessionmaker()
    upserts = 0
    with SessionLocal() as s:
        for rec in iter_jsonl(path):
            # origin_meta or fs holds S3 info
            meta_raw = rec.get("origin_meta") or rec.get("fs")
            fs = None
            try:
                fs = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw) if meta_raw else None
            except Exception:
                fs = None
            fs = (fs or {}).get("fs") or fs or {}
            bucket = (fs.get("bucket") or os.getenv("S3_BUCKET"))
            key = fs.get("key")
            size = fs.get("size")
            etag = fs.get("etag") or fs.get("ETag")
            tenant_id = "default"
            if not key:
                continue
            if args.dry_run:
                log({"kind": "dry_upsert_from_docs", "bucket": bucket, "key": key})
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
