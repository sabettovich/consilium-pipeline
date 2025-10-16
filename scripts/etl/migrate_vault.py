#!/usr/bin/env python3
import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime

from sqlalchemy import select

from src.core.infrastructure.persistence.sqlalchemy.session import get_sessionmaker
from src.core.infrastructure.persistence.sqlalchemy.models import Artifact

REP = Path("doc/etl/etl_report.jsonl")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(8192), b""):
            h.update(ch)
    return h.hexdigest()


def try_parse_main_md(path: str):
    # Expect: <vault>/tenant/<tenant_id>/case/<case_id>/docs/<document_id>.md
    p = Path(path)
    parts = p.parts
    try:
        idx = parts.index("tenant")
        tenant_id = parts[idx + 1]
        if parts[idx + 2] != "case":
            return None
        case_id = parts[idx + 3]
        # .../docs/<document_id>.md
        docs_idx = parts.index("docs")
        doc_fn = parts[docs_idx + 1]
        if not doc_fn.lower().endswith(".md"):
            return None
        document_id = int(Path(doc_fn).stem)
        return tenant_id, case_id, document_id
    except Exception:
        return None


def log(entry: dict):
    REP.parent.mkdir(parents=True, exist_ok=True)
    with REP.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Migrate Vault files into artifacts table (idempotent upsert)")
    ap.add_argument("--root", default=os.getenv("OBSIDIAN_VAULT"), help="Vault root directory")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    root = args.root
    if not root or not Path(root).exists():
        print("ERR: --root or OBSIDIAN_VAULT invalid", file=sys.stderr)
        sys.exit(2)

    SessionLocal = get_sessionmaker()
    processed = 0
    upserted = 0
    with SessionLocal() as s:
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                if not fn.lower().endswith(".md"):
                    continue
                full = str(Path(dirpath) / fn)
                meta = try_parse_main_md(full)
                if not meta:
                    continue
                tenant_id, case_id, document_id = meta
                try:
                    file_sha = sha256_file(full)
                    size = os.path.getsize(full)
                    stmt = select(Artifact).where(
                        Artifact.tenant_id == tenant_id,
                        Artifact.document_id == document_id,
                        Artifact.vault_path == full,
                    )
                    row = s.scalars(stmt).first()
                    if not row:
                        row = Artifact(
                            tenant_id=tenant_id,
                            document_id=document_id,
                            vault_path=full,
                            sha256=file_sha,
                            size=size,
                            metrics=None,
                        )
                        s.add(row)
                        upserted += 1
                    else:
                        if (row.sha256 != file_sha) or (row.size != size):
                            row.sha256 = file_sha
                            row.size = size
                            upserted += 1
                    log({
                        "kind": "vault_artifact_upsert",
                        "tenant_id": tenant_id,
                        "case_id": case_id,
                        "document_id": document_id,
                        "path": full,
                        "sha256": file_sha,
                        "size": size,
                        "ts": datetime.utcnow().isoformat(),
                    })
                    processed += 1
                    if args.limit and processed >= args.limit:
                        break
                except Exception as e:
                    log({
                        "kind": "error_vault_upsert",
                        "path": full,
                        "error": str(e),
                    })
            if args.limit and processed >= args.limit:
                break
        if not args.dry_run:
            s.commit()
    print(json.dumps({"processed": processed, "upserted": upserted}))


if __name__ == "__main__":
    main()
