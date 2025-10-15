import os
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Retries


def create_broker() -> RedisBroker:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    broker = RedisBroker(url=url)
    # Basic retries
    broker.add_middleware(Retries())
    return broker


# Initialize global broker (imported by worker entrypoint)
broker = create_broker()
dramatiq.set_broker(broker)

