# ETL Summary

- cases_created: 3
- cases_updated: 0
- documents_created: 313
- documents_updated: 0
- storage_objects_total: 157
- storage_objects_linked: 155
- s3_indexed: 157
- s3_updated: 155

Details JSONL: `doc/etl/etl_report.jsonl`

Executed scripts:
- scripts/etl/export_old_db.py (tables: docs, matters)
- scripts/etl/migrate_cases.py
- scripts/etl/migrate_documents.py
- scripts/etl/migrate_storage_from_docs.py
- scripts/etl/index_s3.py
- scripts/etl/link_storage_to_doc_case.py
