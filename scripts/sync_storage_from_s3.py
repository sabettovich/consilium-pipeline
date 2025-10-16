#!/usr/bin/env python3
import os
from sqlalchemy import select
from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.models import StorageObject
from src.core.infrastructure.storage.s3_client import create_s3_client

def main():
    s3 = create_s3_client()
    SessionLocal = get_sessionmaker()
    updated = []
    with SessionLocal() as s:
        for so in s.scalars(select(StorageObject)).all():
            bucket = so.bucket or os.getenv('S3_BUCKET')
            try:
                head = s3.head_object(Bucket=bucket, Key=so.key)
                s3_size = int(head.get('ContentLength', 0))
                s3_etag = head.get('ETag', '').strip('"')
                changed = False
                if so.size != s3_size:
                    so.size = s3_size
                    changed = True
                if (so.etag or '') != s3_etag:
                    so.etag = s3_etag
                    changed = True
                if changed:
                    updated.append({'key': so.key, 'size': so.size, 'etag': so.etag})
            except Exception:
                pass
        s.commit()
    print({'updated': updated})

if __name__ == '__main__':
    main()
