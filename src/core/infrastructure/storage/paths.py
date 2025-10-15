import os
from typing import Optional


def vault_root() -> str:
    return os.getenv("OBSIDIAN_VAULT", "./vault")


def vault_main_md_path(tenant_id: str, case_id: str, document_id: int) -> str:
    return os.path.join(vault_root(), "tenant", tenant_id, "case", case_id, "docs", f"{document_id}.md")


def vault_artifact_path(
    tenant_id: str,
    case_id: str,
    document_id: int,
    step: str,
    artifact_id: str,
    ext: str = "md",
) -> str:
    return os.path.join(
        vault_root(),
        "tenant",
        tenant_id,
        "case",
        case_id,
        "docs",
        str(document_id),
        "artifacts",
        step,
        f"{artifact_id}.{ext}",
    )


def s3_original_key(tenant_id: str, case_id: str, filename: str) -> str:
    return f"tenant/{tenant_id}/case/{case_id}/original/{filename}"


def s3_artifact_key(tenant_id: str, case_id: str, step: str, artifact_id: str, filename: Optional[str] = None) -> str:
    tail = filename or f"{artifact_id}"
    return f"tenant/{tenant_id}/case/{case_id}/artifacts/{step}/{tail}"


def s3_final_key(tenant_id: str, case_id: str, document_id: int) -> str:
    return f"tenant/{tenant_id}/case/{case_id}/final/{document_id}.pdf"

