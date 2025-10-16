import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_engine():
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://consilium:consilium@localhost:55432/consilium",
    )
    engine = create_engine(dsn, future=True)
    return engine


def get_sessionmaker():
    engine = get_engine()
    return sessionmaker(bind=engine, future=True)
