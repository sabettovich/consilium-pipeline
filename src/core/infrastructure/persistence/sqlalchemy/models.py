from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenant"

    tenant_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Case(Base):
    __tablename__ = "case"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), index=True)
    case_id = Column(String(128), index=True)
    title = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "case_id", name="uq_case_tenant_caseid"),
    )

    tenant = relationship("Tenant", backref="cases")


class Document(Base):
    __tablename__ = "document"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), index=True)
    case_pk = Column(ForeignKey("case.id", ondelete="RESTRICT"), index=True)

    doc_kind = Column(String(64))
    title = Column(String(512))
    mime = Column(String(128))
    size = Column(Integer)
    sha256 = Column(String(128), index=True)
    storage_ref = Column(String(1024))
    vault_path_main = Column(String(1024))
    idempotency_key = Column(String(256))
    status = Column(String(64), index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_document_tenant_idem"),
        Index("ix_document_tenant_case", "tenant_id", "case_pk"),
    )

    tenant = relationship("Tenant")
    case = relationship("Case")


class Artifact(Base):
    __tablename__ = "artifact"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), index=True)
    document_id = Column(ForeignKey("document.id", ondelete="CASCADE"), index=True)

    kind = Column(String(64))
    vault_path = Column(String(1024))
    sha256 = Column(String(128))
    size = Column(Integer)
    metrics = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_artifact_tenant_doc", "tenant_id", "document_id"),
    )

    tenant = relationship("Tenant")
    document = relationship("Document", backref="artifacts")


class StorageObject(Base):
    __tablename__ = "storage_object"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), index=True)
    bucket = Column(String(255))
    key = Column(String(2048))
    etag = Column(String(128))
    size = Column(Integer)

    document_id = Column(ForeignKey("document.id", ondelete="SET NULL"), nullable=True)
    case_pk = Column(ForeignKey("case.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("bucket", "key", name="uq_storage_object_bucket_key"),
        Index("ix_storage_object_bucket_key", "bucket", "key"),
    )

    tenant = relationship("Tenant")
    document = relationship("Document")
    case = relationship("Case")


class Job(Base):
    __tablename__ = "job"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), index=True)
    document_id = Column(ForeignKey("document.id", ondelete="SET NULL"), nullable=True)
    queue = Column(String(128), index=True)
    status = Column(String(64), index=True)
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant")
    document = relationship("Document")


class Task(Base):
    __tablename__ = "task"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), index=True)
    job_id = Column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    step = Column(String(64))
    status = Column(String(64), index=True)
    attempts = Column(Integer, default=0)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant")
    job = relationship("Job", backref="tasks")


class ProblemLog(Base):
    __tablename__ = "problem_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), index=True)
    document_id = Column(ForeignKey("document.id", ondelete="SET NULL"), nullable=True)
    task_type = Column(String(64))
    queue = Column(String(128))
    error_code = Column(String(64))
    message = Column(Text)
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime)
    trace_id = Column(String(128))
    external_ref = Column(String(256))
    recommendation = Column(Text)
    user_decision = Column(String(64))
    decided_by = Column(String(128))
    decided_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant")
    document = relationship("Document")


class Event(Base):
    __tablename__ = "event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), index=True)
    document_id = Column(ForeignKey("document.id", ondelete="SET NULL"), nullable=True)
    type = Column(String(64), index=True)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant")
    document = relationship("Document")

