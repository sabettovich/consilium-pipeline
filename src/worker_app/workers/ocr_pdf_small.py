import logging
import dramatiq
from src.core.infrastructure.messaging.queues import OCR_PDF_SMALL


@dramatiq.actor(queue_name=OCR_PDF_SMALL)
def ocr_pdf_small(document_id: int) -> None:
    logging.getLogger(__name__).info("ocr_pdf_small: document_id=%s", document_id)
