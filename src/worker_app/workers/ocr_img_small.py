import logging
import dramatiq
from src.core.infrastructure.messaging.queues import OCR_IMG_SMALL


@dramatiq.actor(queue_name=OCR_IMG_SMALL)
def ocr_img_small(document_id: int) -> None:
    logging.getLogger(__name__).info("ocr_img_small: document_id=%s", document_id)
