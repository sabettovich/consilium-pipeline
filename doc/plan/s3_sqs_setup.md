# S3 → SQS настройка для ingestion

## Предпосылки
- Бакет: значение из `S3_BUCKET`
- Аккаунт/ключи: `S3_ACCESS_KEY`, `S3_SECRET_KEY`
- Эндпоинт (R2 или иное S3‑совместимое): `S3_ENDPOINT`

## Очередь SQS
- Создать очередь `ingestion-s3-events` (стандартная).
- Политика очереди (пример, разрешить S3 публиковать события):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowS3ToSend",
      "Effect": "Allow",
      "Principal": {"Service": "s3.amazonaws.com"},
      "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:<region>:<account-id>:ingestion-s3-events",
      "Condition": {"ArnEquals": {"aws:SourceArn": "arn:aws:s3:::<S3_BUCKET>"}}
    }
  ]
}
```

## Уведомления S3 → SQS
- Включить события в бакете `<S3_BUCKET>`:
  - Тип события: `s3:ObjectCreated:*`
  - Цель: очередь SQS `ingestion-s3-events`
  - (Опционально) фильтр по префиксам/суффиксам, если нужно ограничить диапазон

## Переменные окружения (приложение)
- `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_FORCE_PATH_STYLE`
- `REDIS_URL` — для брокера Dramatiq

## Проверка пути
1) Запрос на `POST /documents/presign` — получить `url+fields`
2) Выполнить `curl -F` загрузку файла на S3 (используя presigned POST)
3) Убедиться, что событие попадает в SQS (через консоль/CLI), затем подать это событие в консюмер `handle_s3_event()`

## Локальный прогон консюмера (пример)
- Сохранить пример события в `scripts/examples/s3_event_example.json`
- В коде вызвать:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.infrastructure.messaging.s3_sqs_ingestion import handle_s3_event
import json

engine = create_engine("postgresql+psycopg2://consilium:consilium@localhost:55432/consilium")
Session = sessionmaker(bind=engine)

with open("scripts/examples/s3_event_example.json") as f:
    event = json.load(f)

with Session() as s:
    handle_s3_event(event, s)
```
