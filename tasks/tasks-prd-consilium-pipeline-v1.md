# Tasks: Consilium Pipeline v1 (based on PRD `tasks/prd-consilium-pipeline-v1.md`)

PRD source: `tasks/prd-consilium-pipeline-v1.md`
Rule followed: `doc/rules/generate-tasks.md` (Phase 2 — с подзадачами и Relevant Files)

## Parent Tasks

- [ ] M1. Схема БД и миграции (PostgreSQL)
  - Checkpoint A: модели `tenant, case, document, artifact, storage_object, job, task, problem_log, event` описаны в `src/core/infrastructure/persistence/sqlalchemy/models.py`.
  - Checkpoint B: первичная миграция Alembic создана и применена на dev БД.
  - Checkpoint C: индексы на `idempotency_key`, `(tenant_id, case_id)`, `(bucket, key)` присутствуют.
  - Sub‑tasks:
    - [ ] Описать модели и связи (FK, ON DELETE, уникальные индексы) в `models.py`.
    - [ ] Настроить Alembic (env, script location), сгенерировать initial migration.
    - [ ] Добавить индексы: `idempotency_key`, `(tenant_id, case_id)`, `(bucket, key)`, по `status`.
    - [ ] Подготовить `docker-compose.yml` сервис для Postgres (dev).
    - [ ] Smoke: создать/прочитать `document`, `artifact`, `storage_object`.

- [ ] M2. Брокер и базовые очереди (Redis + Dramatiq)
  - Checkpoint A: Redis как broker и кэш; Dramatiq запускается локально.
  - Checkpoint B: акторы OCR (`ocr_pdf_small`, `ocr_img_small`, `merge_pdf_task`) зарегистрированы.
  - Checkpoint C: базовые ретраи и DLQ брокера включены.
  - Sub‑tasks:
    - [ ] Добавить Redis в compose; конфиг Dramatiq в `dramatiq_broker.py`.
    - [ ] Реализовать `queues.py` (имена, параметры) и регистратор акторов.
    - [ ] Заглушки акторов: `ocr_pdf_small.py`, `ocr_img_small.py`, `merge_pdf_task.py`.
    - [ ] Включить Dramatiq middleware: retries, (опционально) Prometheus.
    - [ ] Health‑actor и health‑endpoint для проверки связности.

- [ ] M3. Интеграция S3→SQS ingestion
  - Checkpoint A: включены события `S3:ObjectCreated:*` → SQS (`ingestion-s3-events`).
  - Checkpoint B: консюмер `s3_sqs_ingestion.py` делает идемпотентную регистрацию документа и маршрутизацию.
  - Checkpoint C: e2e: загрузка → событие → очередь → статус в БД.
  - Sub‑tasks:
    - [ ] Реализовать генерацию presigned PUT/GET (TTL 10 мин) в API.
    - [ ] Настроить S3 Events→SQS (infra‑инструкции) и политику доступа.
    - [ ] Написать консюмера: парсинг события, валидация `(bucket,key,etag,size)`.
    - [ ] Вызов use‑case регистрации документа (идемпотентно) и роутинг по типу/размеру.
    - [ ] Интеграционный тест: multipart upload → событие → постановка в очередь.

- [ ] M4. Идемпотентность и дедупликация
  - Checkpoint A: ключ `sha256+size+type+tenant` вычисляется и сохраняется.
  - Checkpoint B: in-flight guard (Redis) предотвращает дубли параллельных задач.
  - Checkpoint C: upsert по `idempotency_key` в `document`.
  - Sub‑tasks:
    - [ ] Имплементировать сервис `idempotency.py` (вычисление ключа, in‑flight guard).
    - [ ] Upsert стратегии в репозиториях (SQLAlchemy) по `idempotency_key`.
    - [ ] Покрыть тестами коллизии/повторы.

- [ ] M5. Vault индексатор и mapping
  - Checkpoint A: `vault_mapping` и `artifact` наполняются периодическим сканом Vault.
  - Checkpoint B: сверка `sha256/size/mtime`; отчёт несоответствий.
  - Checkpoint C: записи артефактов указывают на валидные `vault_path`.
  - Sub‑tasks:
    - [ ] Реализовать генераторы путей в `paths.py` (Vault/S3) с tenant/case.
    - [ ] Индексатор Vault: рекурсивный скан, хэши, запись `artifact`/`vault_mapping`.
    - [ ] Отчёт расхождений (JSONL + summary), API для запуска индексации.
    - [ ] Конфликты: писать артефакты в `artifacts/`, не трогать `main.md`.

- [ ] M6. Problem Log + ручные перезапуски
  - Checkpoint A: таблица `problem_log` и API `GET/POST /problems`.
  - Checkpoint B: задача из DLQ перезапускается через API с аудированием решения.
  - Checkpoint C: удержание записей 10 дней.
  - Sub‑tasks:
    - [ ] Модель/репозиторий `problem_log` и эндпоинты `problems.py`.
    - [ ] Интеграция с DLQ брокера: извлечение, перезапуск, лог решения.
    - [ ] UI‑черновик (если нужно) или JSON API достаточно.

- [ ] M7. Минимальная наблюдаемость
  - Checkpoint A: структурные логи с `trace_id/document_id`.
  - Checkpoint B: базовые метрики Dramatiq доступны (экспорт Prometheus или экв.).
  - Sub‑tasks:
    - [ ] Логгер в API/акторах с correlation‑полями.
    - [ ] Подключить Prometheus middleware Dramatiq или экспорт метрик.
    - [ ] Дашборд черновой (optional) или curl/Prometheus scrape.

- [ ] M8. ETL миграция из consilium.app
  - Checkpoint A: extract SQLite/S3/Vault; transform mapping; load в Postgres (idempotent upsert).
  - Checkpoint B: отчёты `doc/etl/etl_report.jsonl` и `summary.md`.
  - Sub‑tasks:
    - [ ] `scripts/etl/export_old_db.py` — чтение `consilium.app` SQLite.
    - [ ] `scripts/etl/migrate_db.py` — трансформации и загрузка в Postgres.
    - [ ] `scripts/etl/index_s3.py` — HEAD/etag/size в `storage_object`.
    - [ ] `scripts/etl/migrate_vault.py` — индексация Vault и связывание с документами.
    - [ ] Dry‑run и отчёт несоответствий.

- [ ] M9. Cutover (дельта‑синхра, freeze ≤ 15 мин)
  - Checkpoint A: дельта‑синхронизатор готов, dry‑run выполнен.
  - Checkpoint B: план freeze и smoke‑чеклист составлены.
  - Checkpoint C: репетиция cutover на стейджинге.
  - Sub‑tasks:
    - [ ] Реализовать дельта‑синхронизатор (по updated_at/journal).
    - [ ] Freeze‑план (чёткие шаги, роли, тайминг ≤ 15 минут).
    - [ ] Smoke‑чеклист (загрузка, OCR, Vault, статусы, DLQ).

- [ ] M10. Деплой (простой)
  - Checkpoint A: Docker Compose локально.
  - Checkpoint B: systemd‑юниты для FastAPI, Dramatiq worker, Redis в проде.
  - Sub‑tasks:
    - [ ] Compose‑файл (Postgres, Redis, http_app, worker_app).
    - [ ] systemd service files с Restart=always и логами в journald.
    - [ ] Документация запуска в `README`/`doc/`.

## Relevant Files

- **БД/ORM**
  - `src/core/infrastructure/persistence/sqlalchemy/models.py`
  - `alembic/` миграции (init + versions)

- **Брокер/Очереди**
  - `src/core/infrastructure/messaging/dramatiq_broker.py`
  - `src/core/infrastructure/messaging/queues.py`
  - `src/worker_app/workers/{ocr_pdf_small.py, ocr_img_small.py, merge_pdf_task.py}`

- **S3/SQS ingestion**
  - `src/core/infrastructure/storage/{s3_client.py, paths.py}`
  - `src/core/infrastructure/messaging/s3_sqs_ingestion.py`
  - API presigned: `src/http_app/api/routers/documents.py`

- **Идемпотентность/Роутинг**
  - `src/core/application/services/{idempotency.py, routing.py}`

- **Vault**
  - Индексатор: `src/worker_app/workers/vault_indexer.py` (или `scripts/etl/migrate_vault.py`)
  - Пути: `src/core/infrastructure/storage/paths.py`

- **Problem Log / DLQ**
  - `src/http_app/api/routers/problems.py`
  - `src/core/infrastructure/messaging/dlq_consumer.py`

- **ETL**
  - `scripts/etl/{export_old_db.py, migrate_db.py, index_s3.py, migrate_vault.py}`

- **Наблюдаемость**
  - `src/core/infrastructure/observability/{logging.py, metrics.py}`

- **Деплой**
  - `docker-compose.yml`, `deploy/systemd/*.service`

## Notes

- **Vault — источник истины**: воркеры пишут в `artifacts/…`, консолидация в `main.md` отдельно.
- **S3**: старые ключи не меняем; новые пишем по префиксам `tenant/{tenant}/case/{case}/…`.
- **Безопасность (упрощённо)**: SSE‑S3, Block Public Access, presigned TTL 10 минут.
- **Наблюдаемость (минимум)**: структурные логи, базовые метрики Dramatiq.

