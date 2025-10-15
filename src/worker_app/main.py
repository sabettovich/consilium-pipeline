import logging

# Ensure broker is initialized
from src.core.infrastructure.messaging.dramatiq_broker import broker  # noqa

# Import workers to register actors
from src.worker_app.workers import health  # noqa
from src.worker_app.workers import ocr_pdf_small  # noqa
from src.worker_app.workers import ocr_pdf_large  # noqa
from src.worker_app.workers import ocr_img_small  # noqa
from src.worker_app.workers import merge_pdf_task  # noqa


def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Workers loaded. Start with: dramatiq src.worker_app.main --watch src")


if __name__ == "__main__":
    main()
