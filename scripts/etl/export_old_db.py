#!/usr/bin/env python3
import os
import sys
import json
import argparse
import sqlite3
from pathlib import Path

DEF_OUT = "doc/etl/export"


def export_table(cur, table: str, out_dir: Path, limit: int | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{table}.jsonl"
    count = 0
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    q = f"SELECT * FROM {table}"
    if limit:
        q += f" LIMIT {int(limit)}"
    for row in cur.execute(q):
        obj = {k: row[i] for i, k in enumerate(cols)}
        out_path.write_text("", encoding="utf-8") if count == 0 else None
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        count += 1
    return {"table": table, "rows": count, "path": str(out_path)}


def main():
    ap = argparse.ArgumentParser(description="Export SQLite tables to JSONL")
    ap.add_argument("--sqlite", default=os.getenv("OLD_SQLITE_PATH"), help="Path to SQLite DB")
    ap.add_argument("--out", default=DEF_OUT, help="Output directory for JSONL files")
    ap.add_argument("--tables", nargs="*", help="Specific tables to export")
    ap.add_argument("--limit", type=int, default=None, help="Limit rows per table")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.sqlite:
        print("ERR: --sqlite or OLD_SQLITE_PATH required", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(args.sqlite)
    cur = con.cursor()

    tables = args.tables
    if not tables:
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    if args.dry_run:
        print(json.dumps({"sqlite": args.sqlite, "tables": tables}, ensure_ascii=False, indent=2))
        return

    report = []
    for t in tables:
        try:
            info = export_table(cur, t, out_dir, args.limit)
            report.append(info)
        except Exception as e:
            report.append({"table": t, "error": str(e)})

    print(json.dumps({"export": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
