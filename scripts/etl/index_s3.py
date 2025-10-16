#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path

from sqlalchemy import select

from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.models import StorageObject
from src.core.infrastructure.storage.s3_client import create_s3_client

REP = Path("doc/etl/etl_report.jsonl")


def log(entry: dict):
    REP.parent.mkdir(parents=True, exist_ok=True)
    with REP.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Index S3 (HEAD) and sync to storage_object")
    ap.add_argument("--prefix", default=os.getenv("S3_PREFIX", ""))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    s3 = create_s3_client()
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        print("ERR: S3_BUCKET is not set", file=sys.stderr)
        sys.exit(2)

    SessionLocal = get_sessionmaker()
    total = 0
    updated = 0
    with SessionLocal() as s:
        q = select(StorageObject)
        if args.limit:
            q = q.limit(args.limit)
        rows = list(s.scalars(q).all())
        for so in rows:
            if args.prefix and not str(so.key).startswith(args.prefix):
                continue
            total += 1
            try:
                head = s3.head_object(Bucket=so.bucket or bucket, Key=so.key)
                s3_size = int(head.get("ContentLength", 0))
                s3_etag = head.get("ETag", "").strip('"')
                changed = (so.size != s3_size) or ((so.etag or "") != s3_etag)
                if args.dry_run:
                    log({
                        "kind": "s3_head",
                        "bucket": so.bucket or bucket,
                        "key": so.key,
                        "s3_size": s3_size,
                        "s3_etag": s3_etag,
                        "would_update": changed,
                    })
                    continue
                if changed:
                    so.size = s3_size
                    so.etag = s3_etag
                    updated += 1
            except Exception as e:
                log({
                    "kind": "error_s3_head",
                    "bucket": so.bucket or bucket,
                    "key": so.key,
                    "error": str(e),
                })
        if not args.dry_run:
            s.commit()
    print(json.dumps({"indexed": total, "updated": updated}))


if __name__ == "__main__":
    main()
