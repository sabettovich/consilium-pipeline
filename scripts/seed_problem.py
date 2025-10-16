#!/usr/bin/env python3
from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.repositories import ProblemLogRepository

def main():
    SessionLocal = get_sessionmaker()
    with SessionLocal() as s:
        repo = ProblemLogRepository(s)
        row = repo.add(
            tenant_id="default",
            document_id=None,
            task_type="ingestion",
            queue="health",
            error_code="E_DEMO",
            message="demo problem",
            recommendation="retry",
        )
        s.commit()
        print({"problem_id": row.id})

if __name__ == "__main__":
    main()
