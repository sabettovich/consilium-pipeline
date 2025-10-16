#!/usr/bin/env python3
import json
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from src.core.infrastructure.messaging.s3_sqs_ingestion import handle_s3_event
from src.core.infrastructure.persistence.sqlalchemy.models import StorageObject

DSN = "postgresql+psycopg2://consilium:consilium@localhost:55432/consilium"
EVENT = {
    "Records": [
        {
            "s3": {
                "bucket": {"name": "consilium"},
                "object": {"key": "idem.pdf", "size": 1024, "eTag": "etag-idem"},
            }
        }
    ]
}


def count_storage(engine):
    Session = sessionmaker(bind=engine, future=True)
    with Session() as s:
        return s.scalar(select(func.count()).select_from(StorageObject).where(StorageObject.key == "idem.pdf"))


def main():
    engine = create_engine(DSN, future=True)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as s:
        handle_s3_event(EVENT, s)
        handle_s3_event(EVENT, s)
        c = count_storage(engine)
        so = s.execute(select(StorageObject).where(StorageObject.key == "idem.pdf")).scalars().first()
        print({
            "storage_object_id": so.id if so else None,
            "count_storage_objects": int(c),
        })


if __name__ == "__main__":
    main()
