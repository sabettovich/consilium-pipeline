# Спецификация отказоустойчивой архитектуры юридического конвейера

Источник (первопричина): `doc/plan/idea.md`

Данный документ зафиксирован на основе исходной заметки с идеей и служит стабильной спецификацией для реализации и сопровождения. При расхождениях приоритет за этой спецификацией; исходная заметка остаётся контекстом и историей решений.

## Область

- Конвейер обработки юрдокументов на FastAPI + Dramatiq с Clean Architecture.
- Приоритет: надёжность, отказоустойчивость, наблюдаемость, модульность.

## Принятые решения

### 1) Таксономия очередей и приоритеты
- Размеры: `small ≤ 5 МБ`, `medium 5–20 МБ`, `large 20–100 МБ`, `xlarge > 100 МБ`.
- Типы: `PDF`, `JPG/PNG`, `ODT/DOCX`, `audio`, `video`.
- Имена (примеры): `ocr_pdf_small|medium|large|xlarge`, `ocr_img_small|large`, `parse_doc_small|large`, `asr_audio_small|large`, `ai_text_small|large`, `gen_doc_small|large`, `video_xlarge`.
- Политика: малые — абсолютный приоритет; `large/xlarge` обслуживаются при отсутствии `small`. Для больших PDF — OCR постранично + merge.

### 2) Поток загрузки файлов (S3 → SQS → Ingestion)
- Загрузка: direct-to-S3 (presigned PUT, multipart/resumable).
- События: `s3:ObjectCreated:*` → `SQS (ingestion-s3-events)`.
- Consumer: верифицирует `(bucket, key, etag)`, идемпотентно регистрирует документ, маршрутизирует по типу/размеру.
- Обязательные метаданные: `tenant_id`, `case_id`, `doc_kind`, `original_name`, `mime`, `size`, `sha256`.

### 3) Идемпотентность и дедупликация
- Ключ: `hash(file)+size+type+tenant`.
- In-flight guard (напр., Redis) против параллельных дублей.
- Повторная загрузка возвращает существующий `document_id`.

### 4) DLQ и Журнал проблем
- DLQ: твёрдые ошибки — сразу; временные (сеть/5xx) — после ретраев.
- Хранение DLQ: 10 дней.
- Журнал проблем (Problem Log): `document_id`, `job_id`, `task_type`, `queue`, `error_code`, `message`, `attempts`, `last_attempt_at`, `trace_id`, `external_ref`, `recommendation`, `user_decision`, `decided_by`, `decided_at`.
- Перезапуск: вручную после утверждения пользователем.

### 5) IAM/S3 и ключи объектов
- Безопасность: Block Public Access ON; шифрование `SSE-KMS` (KMS alias `alias/legal-docs`); запрет незашифрованных PUT.
- Префиксы ключей: `tenant/{tenant_id}/case/{case_id}/original/{uuid}-{filename}`, `.../artifacts/{step}/{id}`, `.../final/{document_id}.pdf`.
- Доступ: `presigned PUT/GET` (TTL 10 минут); бакет ограничивает `Content-Type` и размер (≤ 1 ГБ).
- Интеграции: разрешения S3→SQS; consumer с правами `sqs:Receive/Delete`.

### 6) Троттлинг внешних API и ретраи
- Механика: token bucket + ограничение параллелизма per-интеграция, экспоненциальный backoff с полным джиттером, circuit breaker.
- Дефолты:
  - ABBYY OCR: `2 RPS`, `burst 5`, `max_concurrency 4`.
  - Салют Спич: `2 RPS`, `burst 5`, `max_concurrency 3`.
  - LLM (при наличии): `1 RPS`, `burst 2`, `max_concurrency 2`.
- Тайм-ауты/ретраи:
  - small: 30–60с, попыток ≤5, backoff до 2 мин.
  - large: 5–10 мин, попыток ≤4, backoff до 5 мин.
  - xlarge: 20–30 мин, попыток ≤3, backoff до 10 мин.

### 7) Пороговые переключения OCR/ASR (fallback)
- OCR: `coverage < 70%` или `avg_confidence < 0.6` → ABBYY.
- ASR: `avg_confidence < 0.6` или ошибки декодера/VAD → Салют Спич.
- Метрики качества сохраняются для аудита и подбора порогов.

### 8) Событие «принято пользователем» и очистка
- Endpoint: `POST /documents/{id}/accept` (роль оператора).
- Событие: `DocumentAccepted`; промежуточные артефакты очищаются, финальные объекты сохраняются бессрочно в S3.

### 9) Структура директорий (устойчивое ядро)
- Ядро стабильно: `app/domain/`, `app/application/`, `contracts/`, `config/`.
- Заменяемые адаптеры: `app/infrastructure/external/**`, `presentation/workers/**`.
- Версионирование портов: `ports/v1 → v2` без ломки обратной совместимости.
- Конфигурации как данные: `config/queues.yaml`, `retries.yaml`, `throttling.yaml`.

```text
app/
  domain/documents/{entities.py,events.py,policies.py,ports/v1/{ocr.py,asr.py,storage.py,broker.py,problems.py}}
  application/{use_cases/,services/{idempotency.py,routing.py,retries.py,throttling.py,sagas.py},handlers/events.py}
  infrastructure/{persistence/sqlalchemy/,messaging/{dramatiq_broker.py,queues.py,s3_sqs_ingestion.py,dlq_consumer.py},storage/{s3_client.py,paths.py},external/ocr/,external/asr/,observability/,security/}
  presentation/{api/routers/{documents.py,problems.py},workers/{ocr_pdf_small.py,ocr_pdf_large.py,asr_audio_small.py,ai_text_small.py,gen_doc_small.py,merge_pdf_task.py},middleware/{tracing.py,rate_limit.py}}
  contracts/{events/,messages/}
  config/{settings.py,queues.yaml,retries.yaml,throttling.yaml}
  tests/{unit/,integration/with_broker/,integration/with_s3_sqs/,contracts/}
```

## Наблюдаемость
- OpenTelemetry: трассы FastAPI↔Dramatiq, пропагация trace_id.
- Prometheus: метрики Dramatiq + бизнес‑SLI (статусы, длины очередей, ошибки).
- Логи: структурные, корреляция по trace_id/document_id.

## Правила эволюции
- Контракты сообщений — только назад‑совместимые изменения.
- Новые версии портов — рядом (v2) и миграция без ломки ядра.
- Замены адаптеров — через конфиг и контрактные тесты.
