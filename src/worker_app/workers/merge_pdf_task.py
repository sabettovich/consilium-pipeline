import logging
import dramatiq
from src.core.infrastructure.messaging.queues import MERGE_PDF_TASK


@dramatiq.actor(queue_name=MERGE_PDF_TASK)
def merge_pdf_task(document_id: int) -> None:
    logging.getLogger(__name__).info("merge_pdf_task: document_id=%s", document_id)
