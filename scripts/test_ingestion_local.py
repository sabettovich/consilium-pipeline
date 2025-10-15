#!/usr/bin/env python3
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.infrastructure.messaging.s3_sqs_ingestion import handle_s3_event

DSN = "postgresql+psycopg2://consilium:consilium@localhost:55432/consilium"


def main():
    with open("scripts/examples/s3_event_example.json") as f:
        event = json.load(f)
    engine = create_engine(DSN, future=True)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as s:
        handle_s3_event(event, s)
        print("handled")


if __name__ == "__main__":
    main()
