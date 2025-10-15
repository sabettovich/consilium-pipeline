import logging
import dramatiq
from src.core.infrastructure.messaging.queues import HEALTH


@dramatiq.actor(queue_name=HEALTH)
def ping(msg: str = "ok") -> None:
    logging.getLogger(__name__).info("health.ping: %s", msg)
