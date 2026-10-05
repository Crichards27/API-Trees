import json
import time

from redis import Redis

from app.config import settings


redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


EVENT_QUEUE = "api_trees:events"


def schedule_event(
    event_type: str,
    delay_seconds: float,
    **data,
) -> None:

    execute_at = time.time() + delay_seconds

    event = {
        "type": event_type,
        "execute_at": execute_at,
        "data": data,
    }

    redis_client.zadd(
        EVENT_QUEUE,
        {
            json.dumps(event): execute_at
        },
    )


def clear_events() -> None:
    redis_client.delete(EVENT_QUEUE)


def has_scheduled_event(
    event_type: str,
    **data,
) -> bool:
    events = redis_client.zrange(
        EVENT_QUEUE,
        0,
        -1,
    )

    for raw_event in events:
        event = json.loads(raw_event)

        if (
            event.get("type") == event_type
            and event.get("data") == data
        ):
            return True

    return False