import logging
import dramatiq
from src.core.infrastructure.messaging.queues import OCR_PDF_LARGE


@dramatiq.actor(queue_name=OCR_PDF_LARGE)
def ocr_pdf_large(document_id: int) -> None:
    logging.getLogger(__name__).info("ocr_pdf_large: document_id=%s", document_id)
